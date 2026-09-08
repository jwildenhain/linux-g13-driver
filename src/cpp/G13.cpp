#include <iostream>
#include <fstream>
#include <vector>
#include <sys/stat.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <stdlib.h>
#include <unistd.h>
#include <ctime>
#include <chrono>
#include <sys/statvfs.h>
#include <dirent.h>
#include <errno.h>
#include <sstream>
#include <ctype.h>

#include <libusb-1.0/libusb.h>

#include <iomanip>

#include <linux/uinput.h>
#include <fcntl.h>

#include <pthread.h>


#include "Constants.h"
#include "G13.h"
#include "G13Action.h"
#include "PassThroughAction.h"
#include "MacroAction.h"
#include "Output.h"
#include "Font.h"

using namespace std;
static const int LCD_SOURCE_STATS = 0;
static const int LCD_SOURCE_FIFO = 1;
static const int LCD_SOURCE_LOGIFRAME = 2;

void trim(char *s) {
    // Trim spaces and tabs from beginning:
    int i = 0, j;
    while ((s[i] == ' ') || (s[i] == '\t')) {
        i++;
    }
    if (i > 0) {
        for (j = 0; j < strlen(s); j++) {
            s[j] = s[j + i];
        }
        s[j] = '\0';
    }

    // Trim spaces and tabs from end:
    i = strlen(s) - 1;
    while ((s[i] == ' ') || (s[i] == '\t')) {
        i--;
    }
    if (i < (strlen(s) - 1)) {
        s[i + 1] = '\0';
    }
}

static bool parse_color(const char *value, int out[3]) {
    if (value == null) {
        return false;
    }

    char *copy = new char[strlen(value) + 1];
    strcpy(copy, value);

    char *token = strtok(copy, ",");
    if (token == null) {
        delete [] copy;
        return false;
    }

    int c0 = atoi(token);
    token = strtok(null, ",");
    if (token == null) {
        delete [] copy;
        return false;
    }

    int c1 = atoi(token);
    token = strtok(null, ",");
    if (token == null) {
        delete [] copy;
        return false;
    }

    int c2 = atoi(token);
    delete [] copy;

    if (c0 < 0 || c0 > 255 || c1 < 0 || c1 > 255 || c2 < 0 || c2 > 255) {
        return false;
    }

    out[0] = c0;
    out[1] = c1;
    out[2] = c2;
    return true;
}


static bool trim_string(std::string *text) {
    if (text == null) {
        return false;
    }

    while (!text->empty() && isspace((unsigned char)text->front())) {
        text->erase(0, 1);
    }

    while (!text->empty() && isspace((unsigned char)text->back())) {
        text->erase(text->size() - 1, 1);
    }

    return !text->empty();
}

static bool strip_root_partition_suffix(const std::string &raw, std::string *out) {
    size_t begin = raw.find_last_of("/");
    if (begin == std::string::npos || begin + 1 >= raw.size()) {
        return false;
    }

    const std::string base = raw.substr(begin + 1);
    if (base.empty()) {
        return false;
    }

    size_t cut = base.size();
    while (cut > 0 && isdigit((unsigned char)base[cut - 1])) {
        cut--;
    }

    if ((cut < base.size()) && (cut > 0) && (base[cut - 1] == 'p')) {
        cut--;
    }

    if (cut == 0) {
        return false;
    }

    *out = base.substr(0, cut);
    return true;
}

static bool get_root_block_device(std::string *device) {
    std::ifstream mounts("/proc/mounts");
    if (!mounts.is_open()) {
        return false;
    }

    std::string line;
    while (std::getline(mounts, line)) {
        std::istringstream ss(line);
        std::string source;
        std::string mount_point;
        if (!(ss >> source >> mount_point)) {
            continue;
        }

        if (mount_point != "/") {
            continue;
        }

        if (source.find("/dev/") != 0) {
            return false;
        }

        std::string disk;
        if (!strip_root_partition_suffix(source, &disk)) {
            return false;
        }

        *device = disk;
        return true;
    }

    return false;
}

static bool read_text_file(const std::string &path, std::string *value) {
    std::ifstream file(path.c_str());
    if (!file.is_open() || !std::getline(file, *value)) {
        return false;
    }

    return trim_string(value);
}

static bool read_temperature_file(const std::string &path, int *temperature) {
    std::ifstream file(path.c_str());
    long millidegrees = 0;
    if (!file.is_open() || !(file >> millidegrees)) {
        return false;
    }

    if (millidegrees < -50000 || millidegrees > 250000) {
        return false;
    }

    *temperature = (int)((millidegrees >= 0)
            ? ((millidegrees + 500) / 1000)
            : ((millidegrees - 500) / 1000));
    return true;
}

static bool read_hwmon_temperature(const std::string &name_prefix,
        const std::string &preferred_label, int *temperature) {
    bool found = false;
    int best = -1000;

    for (int hwmon = 0; hwmon < 64; hwmon++) {
        std::ostringstream base;
        base << "/sys/class/hwmon/hwmon" << hwmon;

        std::string name;
        if (!read_text_file(base.str() + "/name", &name)
                || name.compare(0, name_prefix.size(), name_prefix) != 0) {
            continue;
        }

        for (int sensor = 1; sensor < 32; sensor++) {
            std::ostringstream prefix;
            prefix << base.str() << "/temp" << sensor;

            if (!preferred_label.empty()) {
                std::string label;
                if (!read_text_file(prefix.str() + "_label", &label)
                        || label != preferred_label) {
                    continue;
                }
            }

            int value = 0;
            if (read_temperature_file(prefix.str() + "_input", &value)) {
                if (!found || value > best) {
                    best = value;
                }
                found = true;
            }
        }
    }

    if (found) {
        *temperature = best;
    }
    return found;
}

static bool read_cpu_temperature(int *temperature) {
    // Tdie excludes AMD's control-temperature offset. Fall back to Tctl on
    // hardware that does not expose a die temperature.
    if (read_hwmon_temperature("k10temp", "Tdie", temperature)) {
        return true;
    }
    if (read_hwmon_temperature("k10temp", "Tctl", temperature)) {
        return true;
    }

    return read_hwmon_temperature("coretemp", "Package id 0", temperature);
}

static bool read_network_temperature(int *temperature) {
    if (read_hwmon_temperature("en", "PHY Temperature", temperature)) {
        return true;
    }
    return read_hwmon_temperature("eth", "PHY Temperature", temperature);
}

static bool read_root_temperature(int *temperature) {
    std::string device;
    if (!get_root_block_device(&device)) {
        return false;
    }

    const std::string hwmon_dir = "/sys/block/" + device + "/device";
    DIR *dir = opendir(hwmon_dir.c_str());
    if (dir == null) {
        return false;
    }

    bool found = false;
    struct dirent *entry = null;
    while ((entry = readdir(dir)) != null) {
        if (strncmp(entry->d_name, "hwmon", 5) != 0) {
            continue;
        }

        const std::string base = hwmon_dir + "/" + entry->d_name;
        std::string label;
        if (read_text_file(base + "/temp1_label", &label)
                && label != "Composite") {
            continue;
        }

        if (read_temperature_file(base + "/temp1_input", temperature)) {
            found = true;
            break;
        }
    }

    closedir(dir);
    return found;
}

void G13::apply_logiframe_page_color() {
    int page = this->logiframe_page;
    if (page < 0 || page >= 4) {
        page = 0;
    }

    int r = this->logiframe_page_colors[page][0];
    int g = this->logiframe_page_colors[page][1];
    int b = this->logiframe_page_colors[page][2];

    if (r < 0 || g < 0 || b < 0) {
        r = this->logiframe_default_color[0];
        g = this->logiframe_default_color[1];
        b = this->logiframe_default_color[2];
    }

    setColor(r, g, b);
}



G13::G13(libusb_device *device) {

    this->device = device;

    this->loaded = 0;

    this->bindings = 0;
    this->mode_profiles = false;
    memset(this->mode_key_down, 0, sizeof(this->mode_key_down));

    this->stick_mode = STICK_KEYS;
    this->last_lcd_update = 0;
    this->prev_cpu_total = 0;
    this->prev_cpu_idle = 0;
    this->prev_net_rx = 0;
    this->prev_net_tx = 0;
    this->prev_disk_read_bytes = 0;
    this->prev_disk_write_bytes = 0;
    this->prev_net_seconds = 0;
    this->prev_disk_seconds = 0;
    this->has_prev_cpu = false;
    this->has_prev_net = false;
    this->has_prev_disk = false;
    this->lcd_source = LCD_SOURCE_STATS;
    this->lcd_fifo_fd = -1;
    this->has_lcd_cache = false;
	this->logiframe_page = 0;
	this->logiframe_page_count = 4;
	this->logiframe_default_color[0] = 128;
	this->logiframe_default_color[1] = 128;
	this->logiframe_default_color[2] = 128;
	for (int i = 0; i < 4; i++) {
		this->logiframe_page_cmds[i] = "";
		this->logiframe_page_colors[i][0] = -1;
		this->logiframe_page_colors[i][1] = -1;
		this->logiframe_page_colors[i][2] = -1;
	} 

    this->lcd_fifo_path = "";
    this->fifo_remainder = "";

    for (int i = 0; i < 5; i++) {
        this->fifo_lines[i] = "";
    }

    for (int i = 0; i < G13_NUM_KEYS; i++) {
        actions[i] = new G13Action();
    }

    if (libusb_open(device, &handle) != 0) {
        cerr << "Error opening G13 device" << endl;
        return;
    }

    if (libusb_kernel_driver_active(handle, 0) == 1) {
        if (libusb_detach_kernel_driver(handle, 0) == 0) {
            cout << "Kernel driver detached" << endl;
        }
    }    int claim_error = libusb_claim_interface(handle, 0);
    if (claim_error < 0) {
        cerr << "Cannot claim interface 0: " << libusb_error_name(claim_error);
        if (claim_error == LIBUSB_ERROR_BUSY) {
            cerr << " (already claimed by another process)";
        } else if (claim_error == LIBUSB_ERROR_ACCESS) {
            cerr << " (permission denied opening USB device node)";
        } else if (claim_error == LIBUSB_ERROR_NOT_FOUND) {
            cerr << " (interface not present)";
        }
        cerr << endl;
        return;
    }

    unsigned char lcd_init_payload[] = { 1 };
    libusb_control_transfer(handle, LIBUSB_REQUEST_TYPE_CLASS | LIBUSB_RECIPIENT_INTERFACE, 9, 0x300, 0, lcd_init_payload,
                            1, 1000);

    memset(this->lcd_buffer, 0, G13_LCD_BUFFER_SIZE);

    setColor(128, 128, 128);

    this->loaded = 1;

}

G13::~G13() {
    if (!this->loaded) {
        return;
    }

    setColor(128, 128, 128);

    // Blank the LCD on the way out, otherwise the last rendered frame stays
    // on the display after the driver stops. Must happen before the interface
    // is released, while the handle is still usable.
    clear_lcd_buffer();
    write_lcd();

    if (this->lcd_fifo_fd >= 0) {
        close(this->lcd_fifo_fd);
        this->lcd_fifo_fd = -1;
    }

    libusb_release_interface(this->handle, 0);
    libusb_close(this->handle);

}

void G13::start() {
    if (!this->loaded) {
        return;
    }

    ifstream brightness_file((string(getenv("HOME")) + "/.g13/brightness").c_str());
    double saved_brightness;
    if ((brightness_file >> saved_brightness) && saved_brightness >= 0 && saved_brightness <= 100) brightness = saved_brightness;
    loadBindings();

    keepGoing = 1;
    render_lcd();
    this->last_lcd_update = time(NULL);

    while (keepGoing && g13_keep_running) {
        if (read() < 0) {
            // Device went away or the transfer failed hard; stop instead of
            // spinning on the same error. The service supervisor restarts us.
            break;
        }
        update_brightness(chrono::duration<double>(chrono::steady_clock::now().time_since_epoch()).count());
        time_t now = time(NULL);
        if ((now - this->last_lcd_update) >= 1) {
            render_lcd();
            this->last_lcd_update = now;
        }
    }
}

void G13::stop() {
    if (!this->loaded) {
        return;
    }

    keepGoing = 0;
}

Macro *G13::loadMacro(int num) {

    char filename[1024];

    sprintf(filename, "%s/.g13/macro-%d.properties", getenv("HOME"), num);
    //cout << "G13::loadMacro(" << num << ") filename=" << filename << "\n";
    ifstream file (filename);

    if (!file.is_open()) {
        cout << "Could not open config file: " << filename << "\n";
        return null;
    }

    Macro *macro = new Macro();
    macro->setId(num);
    while (file.good()) {
        string line;
        getline(file, line);
        //cout << line << "\n";

        char l[1024];
        strcpy(l, (char *)line.c_str());
        trim(l);
        if (strlen(l) > 0 && l[0] != '#') {
            char *key = strtok(l, "=");
            char *value = strtok(NULL, "\n");
            trim(key);
            trim(value);
            //cout << "G13::loadMacro(" << num << ") key=" << key << ", value=" << value << "\n";
            if (strcmp(key, "name") == 0) {
                macro->setName(value);
            }
            else if (strcmp(key, "sequence") == 0) {
                macro->setSequence(value);
            }
        }
    }


    return macro;

}

void G13::loadBindings() {

    char filename[1024];

    sprintf(filename, "%s/.g13/bindings-%d.properties", getenv("HOME"), bindings);
    cout << "loading " << filename << "\n";
    ifstream file (filename);
    if (!file.is_open()) {
        cout << "Could not open config file: " << filename << "\n";
        setColor(128, 128, 128);
        return;
    }

    for (int i = 0; i < G13_NUM_KEYS; i++) {
        if (actions[i] != null) {
            actions[i]->set(0);
            delete actions[i];
        }
        actions[i] = new G13Action();
    }

    for (int i = 0; i < 4; i++) {
        this->logiframe_page_cmds[i] = "";
        this->logiframe_page_colors[i][0] = -1;
        this->logiframe_page_colors[i][1] = -1;
        this->logiframe_page_colors[i][2] = -1;
    }
    this->logiframe_page_count = 4;
    this->logiframe_page = 0;
    this->mode_profiles = false;
    mode_screens = false;
    for (int i = 0; i < 4; i++) page_stats[i] = i == 0;
    stats_poll_seconds = 1;
    stats_average_seconds = 5;
    stats_average.clear();
    stats_lines.clear();
    last_stats_sample = -1;
    prev_threads.clear();
    has_prev_cpu = has_prev_net = has_prev_disk = false;

      while (file.good()) {
          string line;
          getline(file, line);

          vector<char> storage(line.begin(), line.end());
          storage.push_back(0);
          char *l = &storage[0];
          trim(l);
          if (strlen(l) > 0) {
              char *key = strtok(l, "=");
              if (key == null) {
                  continue;
              }
              trim(key);
              if (strlen(key) == 0 || key[0] == '#') {
                  continue;
              }
              else if (strcmp(key, "stats_poll_seconds") == 0 || strcmp(key, "stats_average_seconds") == 0) {
                  bool poll = strcmp(key, "stats_poll_seconds") == 0;
                  char *value = strtok(NULL, " ,\n");
                  int seconds = value ? atoi(value) : 0;
                  if (seconds >= 1 && seconds <= 60) {
                      if (poll) stats_poll_seconds = seconds;
                      else stats_average_seconds = seconds;
                  }
              }
              else if (strcmp(key, "mode_screens") == 0) {
                  char *value = strtok(NULL, " ,\n");
                  mode_screens = value && strcmp(value, "1") == 0;
              }
              else if (strlen(key) == 25 && strncmp(key, "lcd_logiframe_page", 18) == 0 && key[18] >= '1' && key[18] <= '4' && strcmp(key + 19, "_stats") == 0) {
                  int page = key[18] - '1';
                  char *value = strtok(NULL, " ,\n");
                  page_stats[page] = value && strcmp(value, "1") == 0;
              }
              else if (strcmp(key, "mode_profiles") == 0) {
                  char *value = strtok(NULL, " ,\n");
                  this->mode_profiles = value && strcmp(value, "1") == 0;
              }
              else if (strcmp(key, "lcd_source") == 0 || strcmp(key, "lcd_mode") == 0) {
                  char *mode = strtok(NULL, " ,\n");
                  if (mode == null) {
                      cout << "G13::loadBindings() missing lcd_source value\n";
                      continue;
                  }
                  trim(mode);
                  if (strncmp(mode, "fifo", 4) == 0 || strncmp(mode, "logiframe", 9) == 0) {
                      char *path = strchr(mode, ':');
                      if (path != null) {
                          path++;
                          set_lcd_source((strncmp(mode, "logiframe", 9) == 0) ? "logiframe" : "fifo", path);
                      }
                      else {
                          set_lcd_source(strncmp(mode, "logiframe", 9) == 0 ? "logiframe" : "fifo", "");
                      }
                  }
                  else {
                      set_lcd_source(mode, "");
                  }
              }
              else if (strcmp(key, "lcd_path") == 0 || strcmp(key, "lcd_fifo") == 0) {
                  char *path = strtok(NULL, "\n");
                  if (path == null) {
                      cout << "G13::loadBindings() missing lcd_path value\n";
                      continue;
                  }
                  trim(path);
                  set_lcd_source("fifo", path);
              }
              else if (strcmp(key, "lcd_logiframe_page_count") == 0) {
                  char *count = strtok(NULL, "\n");
                  if (count != null) {
                      int parsed = atoi(count);
                      if (parsed >= 1 && parsed <= 4) {
                          this->logiframe_page_count = parsed;
                      }
                  }
              }
              else if (strcmp(key, "lcd_logiframe_page1_cmd") == 0 ||
                      strcmp(key, "lcd_page1_cmd") == 0 ||
                      strcmp(key, "lcd_logiframe_usage_cmd") == 0) {
                  char *cmd = strtok(NULL, "\n");
                  if (cmd != null) {
                      trim(cmd);
                      this->logiframe_page_cmds[0] = cmd;
                  }
              }
              else if (strcmp(key, "lcd_logiframe_page2_cmd") == 0 ||
                      strcmp(key, "lcd_page2_cmd") == 0 ||
                      strcmp(key, "lcd_logiframe_steam_cmd") == 0) {
                  char *cmd = strtok(NULL, "\n");
                  if (cmd != null) {
                      trim(cmd);
                      this->logiframe_page_cmds[1] = cmd;
                  }
              }
              else if (strcmp(key, "lcd_logiframe_page3_cmd") == 0 ||
                      strcmp(key, "lcd_page3_cmd") == 0 ||
                      strcmp(key, "lcd_logiframe_tokens_cmd") == 0) {
                  char *cmd = strtok(NULL, "\n");
                  if (cmd != null) {
                      trim(cmd);
                      this->logiframe_page_cmds[2] = cmd;
                  }
              }
              else if (strcmp(key, "lcd_logiframe_page4_cmd") == 0 ||
                      strcmp(key, "lcd_page4_cmd") == 0) {
                  char *cmd = strtok(NULL, "\n");
                  if (cmd != null) {
                      trim(cmd);
                      this->logiframe_page_cmds[3] = cmd;
                  }
              }
              else if (strcmp(key, "lcd_logiframe_page1_color") == 0 || strcmp(key, "lcd_page1_color") == 0) {
                  char *color_text = strtok(NULL, "\n");
                  if (color_text != null) {
                      int color[3];
                      trim(color_text);
                      if (parse_color(color_text, color)) {
                          this->logiframe_page_colors[0][0] = color[0];
                          this->logiframe_page_colors[0][1] = color[1];
                          this->logiframe_page_colors[0][2] = color[2];
                      }
                  }
              }
              else if (strcmp(key, "lcd_logiframe_page2_color") == 0 || strcmp(key, "lcd_page2_color") == 0) {
                  char *color_text = strtok(NULL, "\n");
                  if (color_text != null) {
                      int color[3];
                      trim(color_text);
                      if (parse_color(color_text, color)) {
                          this->logiframe_page_colors[1][0] = color[0];
                          this->logiframe_page_colors[1][1] = color[1];
                          this->logiframe_page_colors[1][2] = color[2];
                      }
                  }
              }
              else if (strcmp(key, "lcd_logiframe_page3_color") == 0 || strcmp(key, "lcd_page3_color") == 0) {
                  char *color_text = strtok(NULL, "\n");
                  if (color_text != null) {
                      int color[3];
                      trim(color_text);
                      if (parse_color(color_text, color)) {
                          this->logiframe_page_colors[2][0] = color[0];
                          this->logiframe_page_colors[2][1] = color[1];
                          this->logiframe_page_colors[2][2] = color[2];
                      }
                  }
              }
              else if (strcmp(key, "lcd_logiframe_page4_color") == 0 || strcmp(key, "lcd_page4_color") == 0) {
                  char *color_text = strtok(NULL, "\n");
                  if (color_text != null) {
                      int color[3];
                      trim(color_text);
                      if (parse_color(color_text, color)) {
                          this->logiframe_page_colors[3][0] = color[0];
                          this->logiframe_page_colors[3][1] = color[1];
                          this->logiframe_page_colors[3][2] = color[2];
                      }
                  }
              }
              else if (strcmp(key, "color") == 0) {
                  char *color_text = strtok(NULL, "\n");
                  if (color_text == null) {
                      cout << "G13::loadBindings() malformed color for " << key << "\n";
                      continue;
                  }
                  int color[3];
                  trim(color_text);
                  if (parse_color(color_text, color)) {
                      this->logiframe_default_color[0] = color[0];
                      this->logiframe_default_color[1] = color[1];
                      this->logiframe_default_color[2] = color[2];
                      setColor(color[0], color[1], color[2]);
                  }
                  else {
                      cout << "G13::loadBindings() malformed color for " << key << "\n";
                  }
              }
              else if (strcmp(key, "mod") == 0 || strcmp(key, "mod_leds") == 0 || strcmp(key, "mode_leds") == 0) {
                  char *num = strtok(NULL, ",\n ");
                  if (num == null) {
                      cout << "G13::loadBindings() malformed mod value for " << key << "\n";
                      continue;
                  }
                  trim(num);
                  const int leds = atoi(num);
                  if (leds < 0 || leds > 15) {
                      cout << "G13::loadBindings() mod value out of range (0-15) for " << key << "\n";
                      continue;
                  }
                  setModeLeds(leds);
              }
              else if (strcmp(key, "stick_mode") == 0) {
                  char *mode = strtok(NULL, ",\n ");
                  if (mode == null) {
                      cout << "G13::loadBindings() missing stick_mode value\n";
                      continue;
                  }

                  trim(mode);
                  if (strcmp(mode, "0") == 0 || strcmp(mode, "keys") == 0) {
                      stick_mode = STICK_KEYS;
                  }
                  else if (strcmp(mode, "1") == 0 || strcmp(mode, "absolute") == 0) {
                      stick_mode = STICK_ABSOLUTE;
                  }
                  else {
                      cout << "G13::loadBindings() unknown stick_mode '" << mode << "'\n";
                  }
              }
              else {
                  const char *binding_key = key;
                  if (strcmp(binding_key, "STICK_UP") == 0) {
                      binding_key = "G36";
                  }
                  else if (strcmp(binding_key, "STICK_LEFT") == 0) {
                      binding_key = "G37";
                  }
                  else if (strcmp(binding_key, "STICK_RIGHT") == 0) {
                      binding_key = "G38";
                  }
                  else if (strcmp(binding_key, "STICK_DOWN") == 0) {
                      binding_key = "G39";
                  }
                  else if (strcmp(binding_key, "M1") == 0) {
                      binding_key = "G29";
                  }
                  else if (strcmp(binding_key, "M2") == 0) {
                      binding_key = "G30";
                  }
                  else if (strcmp(binding_key, "M3") == 0) {
                      binding_key = "G31";
                  }
                  else if (strcmp(binding_key, "M4") == 0 || strcmp(binding_key, "MR") == 0) {
                      binding_key = "G32";
                  }
                  else if (strcmp(binding_key, "LEFT") == 0) {
                      binding_key = "G33";
                  }
                  else if (strcmp(binding_key, "DOWN") == 0) {
                      binding_key = "G34";
                  }
                  else if (strcmp(binding_key, "TOP") == 0) {
                      binding_key = "G35";
                  }

                  if (binding_key[0] == 'G') {
                      int gKey = atoi(&binding_key[1]);
                      if (gKey < 0 || gKey >= G13_NUM_KEYS) {
                          cout << "G13::loadBindings() invalid G-key " << gKey << "\n";
                          continue;
                      }
                      char *type = strtok(NULL, ",");
                      if (type == null) {
                          cout << "G13::loadBindings() malformed binding for " << binding_key << "\n";
                          continue;
                      }
                      trim(type);
                      if (strcmp(type, "p") == 0) {
                          char *keytype = strtok(NULL, ",\n ");
                          if (keytype == null) {
                              cout << "G13::loadBindings() malformed passthrough binding for G" << gKey << "\n";
                              continue;
                          }
                          trim(keytype);

                          int keycode = 0;
                          if (strncmp(keytype, "k.", 2) == 0) {
                              keycode = atoi(&keytype[2]);
                          }
                          else {
                              keycode = atoi(keytype);
                          }

                          G13Action *action = new PassThroughAction(keycode);
                          actions[gKey] = action;
                      }
                      else if (strcmp(type, "m") == 0) {
                          char *macroToken = strtok(NULL, ",\n ");
                          if (macroToken == null) {
                              cout << "G13::loadBindings() malformed macro binding for G" << gKey << "\n";
                              continue;
                          }

                          int macroId = atoi(macroToken);
                          int repeats = 0;
                          char *repeatToken = strtok(NULL, ",\n ");
                          if (repeatToken != null) {
                              repeats = atoi(repeatToken);
                          }
                          Macro *macro = loadMacro(macroId);
                          if (macro == null) {
                              cout << "G13::loadBindings() cannot load macro " << macroId << "\n";
                              continue;
                          }
                          MacroAction *action = new MacroAction(macro->getSequence());
                          action->setRepeats(repeats);
                          actions[gKey] = action;
                          delete macro;
                      }
                      else {
                          cout << "G13::loadBindings() unknown type '" << type << "'\n";
                      }

                  }
                  else {
                      cout << "G13::loadBindings() Unknown first token: " << key << "\n";
                  }


          }

          //cout << line << endl;
      }

      } // finish reading all properties before closing the file
      file.close();
      if (this->mode_profiles && this->lcd_source == LCD_SOURCE_LOGIFRAME) {
          set_logiframe_page(mode_screens ? selected_pages[this->bindings] : this->bindings);
      }
}

void G13::setColor(int red, int green, int blue) {
    int error;
    unsigned char usb_data[] = { 5, 0, 0, 0, 0 };
    backlight_base[0] = red; backlight_base[1] = green; backlight_base[2] = blue;
    usb_data[1] = static_cast<unsigned char>(red * brightness / 100.0 + 0.5);
    usb_data[2] = static_cast<unsigned char>(green * brightness / 100.0 + 0.5);
    usb_data[3] = static_cast<unsigned char>(blue * brightness / 100.0 + 0.5);

    error = libusb_control_transfer(handle, LIBUSB_REQUEST_TYPE_CLASS | LIBUSB_RECIPIENT_INTERFACE, 9, 0x307, 0,
            usb_data, 5, 1000);

    if (error != 5) {
        cerr << "Problem sending data" << endl;
    }

}

void G13::update_brightness(double now) {
    if (!brightness_held || now < brightness_started + 0.4) return;
    double start = brightness_updated > brightness_started + 0.4 ? brightness_updated : brightness_started + 0.4;
    double remaining = (now - start) * 20.0; // Five seconds from minimum to maximum.
    if (remaining <= 0) return;
    while (remaining > 0) {
        double distance = brightness_direction > 0 ? 100 - brightness : brightness;
        double step = remaining < distance ? remaining : distance;
        brightness += brightness_direction * step;
        remaining -= step;
        if (step >= distance) brightness_direction = -brightness_direction;
    }
    brightness_updated = now;
    setColor(backlight_base[0], backlight_base[1], backlight_base[2]);
}

void G13::save_brightness() {
    string path = string(getenv("HOME")) + "/.g13/brightness";
    string temporary = path + ".tmp";
    ofstream file(temporary.c_str());
    if (!file.is_open()) return;
    file << brightness << "\n";
    file.close();
    if (file.fail()) { unlink(temporary.c_str()); return; }
    chmod(temporary.c_str(), 0600);
    if (rename(temporary.c_str(), path.c_str()) != 0) unlink(temporary.c_str());
}

void G13::set_lcd_source(const string &mode, const string &path) {
    if (mode == "stats" || mode == "system" || mode == "default" || mode == "sys") {
        if (this->lcd_fifo_fd >= 0) {
            close(this->lcd_fifo_fd);
            this->lcd_fifo_fd = -1;
        }
        this->lcd_fifo_path = "";
        this->fifo_remainder = "";
        this->has_lcd_cache = false;
        this->lcd_source = LCD_SOURCE_STATS;
        return;
    }

    if (mode == "fifo") {
        this->lcd_source = LCD_SOURCE_FIFO;
        if (!path.empty()) {
            this->lcd_fifo_path = path;
            this->fifo_remainder = "";
            this->has_lcd_cache = false;
        }

        if (this->lcd_fifo_path.empty()) {
            if (this->lcd_fifo_fd >= 0) {
                close(this->lcd_fifo_fd);
                this->lcd_fifo_fd = -1;
            }
            this->fifo_remainder = "";
            this->has_lcd_cache = false;
            return;
        }

        setup_lcd_fifo(this->lcd_fifo_path);
        return;
    }

    if (mode == "logiframe") {
        if (this->lcd_fifo_fd >= 0) {
            close(this->lcd_fifo_fd);
            this->lcd_fifo_fd = -1;
        }

        this->lcd_fifo_path = "";
        this->fifo_remainder = "";
        this->has_lcd_cache = false;
        if (this->logiframe_page_count <= 0 || this->logiframe_page_count > 4) {
            this->logiframe_page_count = 4;
        }
        this->lcd_source = LCD_SOURCE_LOGIFRAME;
        set_logiframe_page(0);
        return;
    }

    cout << "G13::set_lcd_source() unknown mode: " << mode << ", using stats\n";
    this->lcd_source = LCD_SOURCE_STATS;
}

bool G13::setup_lcd_fifo(const string &path) {
    if (this->lcd_fifo_fd >= 0) {
        close(this->lcd_fifo_fd);
        this->lcd_fifo_fd = -1;
    }

    if (path.empty()) {
        return false;
    }

    int fd = open(path.c_str(), O_RDONLY | O_NONBLOCK);
    if (fd < 0) {
        cerr << "Could not open LCD FIFO " << path << ": " << errno << "\n";
        return false;
    }

    this->lcd_fifo_fd = fd;
    this->lcd_fifo_path = path;
    this->fifo_remainder = "";
    this->has_lcd_cache = false;

    return true;
}
void G13::cache_fifo_lines(const string &text) {
    string combined = this->fifo_remainder + text;
    size_t line_start = 0;
    int line_index = 0;
    bool had_line = false;

    while (true) {
        size_t newline = combined.find('\n', line_start);
        if (newline == string::npos) {
            break;
        }

        string line = combined.substr(line_start, newline - line_start);
        if (!line.empty() && line[line.size() - 1] == '\r') {
            line = line.substr(0, line.size() - 1);
        }

        if (line_index < 5) {
            this->fifo_lines[line_index++] = line;
        }
        else {
            line_index++;
        }

        had_line = true;
        line_start = newline + 1;
    }

    this->fifo_remainder = combined.substr(line_start);

    if (had_line && line_index > 0) {
        for (int i = line_index; i < 5; i++) {
            this->fifo_lines[i] = "";
        }
        this->has_lcd_cache = true;
    }
}

bool G13::render_fifo_to_lcd() {
    if (this->lcd_fifo_path.empty()) {
        return false;
    }

    if (this->lcd_fifo_fd < 0) {
        if (!setup_lcd_fifo(this->lcd_fifo_path)) {
            return this->has_lcd_cache;
        }
    }

    char buffer[256];
    ssize_t n = ::read(this->lcd_fifo_fd, buffer, sizeof(buffer) - 1);
    if (n > 0) {
        buffer[n] = '\0';
        cache_fifo_lines(string(buffer));
    }
    else if (n == 0) {
        close(this->lcd_fifo_fd);
        this->lcd_fifo_fd = -1;
        this->fifo_remainder = "";
    }
    else if (errno != EAGAIN && errno != EWOULDBLOCK) {
        close(this->lcd_fifo_fd);
        this->lcd_fifo_fd = -1;
        this->fifo_remainder = "";
    }

    if (!this->has_lcd_cache) {
        return false;
    }

    clear_lcd_buffer();
    for (int i = 0; i < 5; i++) {
        write_text(0, i * 8, this->fifo_lines[i]);
    }
    write_lcd();
    return true;
}

bool G13::render_lcd() {
    if (this->lcd_source == LCD_SOURCE_LOGIFRAME) {
        render_logiframe_page();
        return true;
    }

    if (this->lcd_source == LCD_SOURCE_FIFO) {
        if (render_fifo_to_lcd()) {
            return true;
        }
    }

    render_stats_to_lcd();
    return true;
}
void G13::clear_lcd_buffer() {
    memset(this->lcd_buffer, 0, G13_LCD_BUFFER_SIZE);
}

void G13::setModeLeds(int leds) {
    if (!this->loaded) {
        return;
    }

    if (leds < 0) {
        leds = 0;
    }
    else if (leds > 15) {
        leds = 15;
    }

    int error;
    unsigned char usb_data[] = { 5, 0, 0, 0, 0 };
    usb_data[1] = leds & 0x0f;

    error = libusb_control_transfer(handle, LIBUSB_REQUEST_TYPE_CLASS | LIBUSB_RECIPIENT_INTERFACE, 9, 0x305, 0,
            usb_data, 5, 1000);

    if (error != 5) {
        cerr << "Problem sending mode LED data" << endl;
    }
}

void G13::set_pixel(int x, int y, bool on) {
    if (x < 0 || x >= 160 || y < 0 || y >= 43) {
        return;
    }

    int index = x + (y / 8) * 160;
    int bit = y % 8;

    if (on) {
        this->lcd_buffer[index] |= (1 << bit);
    }
    else {
        this->lcd_buffer[index] &= ~(1 << bit);
    }
}

void G13::write_lcd() {
    if (!this->loaded) {
        return;
    }

    unsigned char buffer[G13_LCD_BUFFER_SIZE + 32];
    memset(buffer, 0, sizeof(buffer));
    buffer[0] = 0x03;
    memcpy(buffer + 32, this->lcd_buffer, G13_LCD_BUFFER_SIZE);

    int size = 0;
    int error = libusb_interrupt_transfer(this->handle, G13_LCD_ENDPOINT | LIBUSB_ENDPOINT_OUT, buffer,
            sizeof(buffer), &size, 1000);

    if (error) {
        cerr << "Problem sending LCD data: " << error << endl;
    }
}

void G13::write_char(int x, int y, char c) {
    if (static_cast<unsigned char>(c) < 32 || static_cast<unsigned char>(c) > 126) {
        c = 32;
    }

    int font_index = (c - 32) * 5;
    for (int col = 0; col < 5; col++) {
        uint8_t line = font_5x7[font_index + col];

        for (int row = 0; row < 7; row++) {
            if ((line & (1 << row)) != 0) {
                set_pixel(x + col, y + row, true);
            }
        }
    }
}

void G13::write_text(int x, int y, const std::string &text) {
    int cursor_x = x;

    for (int i = 0; i < (int)text.size(); i++) {
        if (cursor_x > 154) {
            break;
        }

        write_char(cursor_x, y, text[i]);
        cursor_x += 6;
    }
}

bool G13::read_cpu_sample(unsigned long long *total, unsigned long long *idle) {
    ifstream file("/proc/stat");
    if (!file.is_open()) {
        return false;
    }

    string line;
    if (!getline(file, line)) {
        return false;
    }

    if (strncmp(line.c_str(), "cpu", 3) != 0) {
        return false;
    }

    stringstream ss(line);
    string label;
    ss >> label;

    unsigned long long values[10];
    int count = 0;
    while ((count < 10) && (ss >> values[count])) {
        count++;
    }

    if (count < 4) {
        return false;
    }

    unsigned long long totalValue = 0;
    for (int i = 0; i < count; i++) {
        totalValue += values[i];
    }

    *total = totalValue;
    *idle = values[3];
    if (count > 4) {
        *idle += values[4];
    }

    return true;
}

int G13::read_active_threads(const string &path) {
    ifstream file(path);
    if (!file.is_open()) {
        prev_threads.clear();
        return -1;
    }
    map<string, pair<unsigned long long, unsigned long long> > current;
    string line;
    int active = 0, compared = 0;
    while (getline(file, line)) {
        istringstream input(line);
        string name;
        input >> name;
        if (name.size() < 4 || name.compare(0, 3, "cpu") != 0 || !isdigit(name[3])) continue;
        unsigned long long values[8] = {}, total = 0;
        int count = 0;
        while (count < 8 && (input >> values[count])) count++;
        if (count < 4) continue;
        // Guest counters beyond these eight fields are already included in user/nice.
        for (int i = 0; i < count; i++) total += values[i];
        unsigned long long idle = values[3] + values[4];
        current[name] = make_pair(total, idle);
        auto previous = prev_threads.find(name);
        if (previous == prev_threads.end()) continue;
        if (total <= previous->second.first || idle < previous->second.second) continue;
        unsigned long long dt = total - previous->second.first;
        unsigned long long di = idle - previous->second.second;
        if (di > dt) continue;
        compared++;
        if (static_cast<double>(dt - di) / dt > 0.05) active++;
    }
    prev_threads.swap(current);
    return compared ? active : -1;
}

int G13::read_psu_watts(const string &root) {
    // Identify the PSU and its total-power label, never sum independently sampled rails.
    for (int h = 0; h < 64; h++) {
        string base = root + "/hwmon" + to_string(h);
        string name;
        if (!read_text_file(base + "/name", &name) || name != "corsairpsu") continue;
        for (int sensor = 1; sensor < 32; sensor++) {
            string prefix = base + "/power" + to_string(sensor);
            string label;
            if (!read_text_file(prefix + "_label", &label) || label != "power total") continue;
            ifstream input(prefix + "_input");
            long long microwatts;
            if ((input >> microwatts) && microwatts >= 0 && microwatts <= 1000000000000LL)
                return static_cast<int>((microwatts + 500000) / 1000000);
        }
    }
    return -1;
}

bool G13::read_mem_percent(int *percent) {
    ifstream file("/proc/meminfo");
    if (!file.is_open()) {
        return false;
    }

    unsigned long long mem_total = 0;
    unsigned long long mem_free = 0;
    unsigned long long mem_buffers = 0;
    unsigned long long mem_cached = 0;
    unsigned long long mem_available = 0;

    string line;
    while (getline(file, line)) {
        string key;
        unsigned long long value;

        if (sscanf(line.c_str(), "MemTotal: %llu kB", &value) == 1) {
            mem_total = value;
        }
        else if (sscanf(line.c_str(), "MemFree: %llu kB", &value) == 1) {
            mem_free = value;
        }
        else if (sscanf(line.c_str(), "MemAvailable: %llu kB", &value) == 1) {
            mem_available = value;
        }
        else if (sscanf(line.c_str(), "Buffers: %llu kB", &value) == 1) {
            mem_buffers = value;
        }
        else if (sscanf(line.c_str(), "Cached: %llu kB", &value) == 1) {
            mem_cached = value;
        }
    }

    if (mem_total == 0) {
        return false;
    }

    unsigned long long used_kb;
    if (mem_available > 0) {
        used_kb = (mem_total > mem_available) ? (mem_total - mem_available) : 0;
    }
    else {
        unsigned long long reclaimable = mem_free + mem_buffers + mem_cached;
        used_kb = (mem_total > reclaimable) ? (mem_total - reclaimable) : 0;
    }

    *percent = (int)((used_kb * 100ULL) / mem_total);
    return true;
}

bool G13::read_disk_percent(int *percent) {
    struct statvfs st;
    if (statvfs("/", &st) != 0) {
        return false;
    }

    if (st.f_blocks == 0) {
        return false;
    }

    unsigned long long total = st.f_blocks;
    unsigned long long available = st.f_bavail;
    unsigned long long used = (total > available) ? (total - available) : 0;

    *percent = (int)((used * 100ULL) / total);
    return true;
}

bool G13::read_disk_io_bytes(unsigned long long *read_bytes, unsigned long long *write_bytes) {
    std::string device;
    if (!get_root_block_device(&device)) {
        return false;
    }

    std::ifstream file("/proc/diskstats");
    if (!file.is_open()) {
        return false;
    }

    std::string line;
    while (std::getline(file, line)) {
        std::istringstream ss(line);
        unsigned int major = 0;
        unsigned int minor = 0;
        std::string name;

        unsigned long long rd_ios = 0;
        unsigned long long rd_merges = 0;
        unsigned long long rd_sectors = 0;
        unsigned long long rd_ticks = 0;
        unsigned long long wr_ios = 0;
        unsigned long long wr_merges = 0;
        unsigned long long wr_sectors = 0;
        unsigned long long wr_ticks = 0;

        if (!(ss >> major >> minor >> name)) {
            continue;
        }

        if (name != device) {
            continue;
        }

        if (!(ss >> rd_ios >> rd_merges >> rd_sectors >> rd_ticks)) {
            continue;
        }
        if (!(ss >> wr_ios >> wr_merges >> wr_sectors >> wr_ticks)) {
            continue;
        }

        *read_bytes = rd_sectors * 512ULL;
        *write_bytes = wr_sectors * 512ULL;
        return true;
    }

    return false;
}

bool G13::read_disk_io_speed(unsigned long long *read_per_sec, unsigned long long *write_per_sec) {
    unsigned long long read_bytes = 0;
    unsigned long long write_bytes = 0;

    if (!read_disk_io_bytes(&read_bytes, &write_bytes)) {
        return false;
    }

    time_t now = time(NULL);
    if (this->has_prev_disk && (now > this->prev_disk_seconds)) {
        unsigned long long delta_seconds = now - this->prev_disk_seconds;
        unsigned long long delta_read = (read_bytes >= this->prev_disk_read_bytes)
                ? (read_bytes - this->prev_disk_read_bytes)
                : 0;
        unsigned long long delta_write = (write_bytes >= this->prev_disk_write_bytes)
                ? (write_bytes - this->prev_disk_write_bytes)
                : 0;

        *read_per_sec = (delta_seconds > 0) ? (delta_read / delta_seconds) : 0;
        *write_per_sec = (delta_seconds > 0) ? (delta_write / delta_seconds) : 0;
    }
    else {
        *read_per_sec = 0;
        *write_per_sec = 0;
    }

    this->prev_disk_read_bytes = read_bytes;
    this->prev_disk_write_bytes = write_bytes;
    this->prev_disk_seconds = now;
    this->has_prev_disk = true;

    return true;
}

static long long gpu_number(const string &field) {
    istringstream input(field);
    long long value;
    if (!(input >> value) || value < 0) return -1;
    input >> ws;
    return input.eof() ? value : -1;
}

string G13::format_gpu_line(long long usage, long long used, long long total, long long temperature, double sample_time) {
    long long percent = used >= 0 && total > 0 ? (used >= total ? 100 : static_cast<int>(100.0 * used / total + 0.5)) : -1;
    if (sample_time >= 0) {
        usage = lround(stats_average.add("gpu", usage, sample_time, stats_average_seconds));
        percent = lround(stats_average.add("vram", percent, sample_time, stats_average_seconds));
        temperature = lround(stats_average.add("gpu_temp", temperature, sample_time, stats_average_seconds));
    }
    string gpu = usage >= 0 ? to_string(usage > 100 ? 100 : usage) + "%" : "n/a";
    string memory = "n/a";
    if (percent >= 0) {
        memory = to_string(percent) + "%";
    }
    string temp = temperature >= 0 && temperature <= 999 ? to_string(temperature) + "C" : "n/a";
    return "GPU " + gpu + " MEM " + memory + " " + temp;
}

bool G13::read_gpu_line(string *text, double sample_time) {
    char buffer[256];
    FILE *fp = popen("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits 2>/dev/null", "r");
    if (fp != null) {
        bool available = false;
        if (fgets(buffer, sizeof(buffer), fp) != null) {
            istringstream csv(buffer);
            string field;
            long long values[4] = {-1, -1, -1, -1};
            for (int i = 0; i < 4 && getline(csv, field, ','); i++) {
                values[i] = gpu_number(field);
            }
            available = values[0] >= 0 || (values[1] >= 0 && values[2] > 0) || values[3] >= 0;
            if (available) *text = format_gpu_line(values[0], values[1], values[2], values[3], sample_time);
        }
        pclose(fp);
        if (available) return true;
    }

    for (int i = 0; i < 3; i++) {
        string device = "/sys/class/drm/card" + to_string(i) + "/device";
        ifstream busy(device + "/gpu_busy_percent");
        long long usage = -1;
        if (!(busy >> usage) || usage < 0) continue;

        long long used = -1, total = -1;
        ifstream used_file(device + "/mem_info_vram_used");
        ifstream total_file(device + "/mem_info_vram_total");
        used_file >> used;
        total_file >> total;
        int temperature = -1;
        DIR *dir = opendir((device + "/hwmon").c_str());
        if (dir != null) {
            struct dirent *entry;
            while ((entry = readdir(dir)) != null) {
                if (strncmp(entry->d_name, "hwmon", 5) == 0 &&
                    read_temperature_file(device + "/hwmon/" + entry->d_name + "/temp1_input", &temperature)) break;
            }
            closedir(dir);
        }
        *text = format_gpu_line(usage, used, total, temperature, sample_time);
        return true;
    }
    return false;
}

bool G13::read_net_sample(unsigned long long *rx, unsigned long long *tx) {
    ifstream file("/proc/net/dev");
    if (!file.is_open()) {
        return false;
    }

    unsigned long long rx_total = 0;
    unsigned long long tx_total = 0;

    string line;
    if (!getline(file, line)) {
        return false;
    }
    if (!getline(file, line)) {
        return false;
    }

    while (getline(file, line)) {
        size_t colon = line.find(":");
        if (colon == string::npos) {
            continue;
        }

        string iface = line.substr(0, colon);
        size_t start = iface.find_first_not_of(" 	");
        if (start == string::npos) {
            continue;
        }
        size_t end = iface.find_last_not_of(" 	");
        iface = iface.substr(start, end - start + 1);

        if (iface == "lo") {
            continue;
        }

        string stats = line.substr(colon + 1);
        stringstream ss(stats);
        unsigned long long rx_bytes = 0;
        unsigned long long tx_bytes = 0;
        unsigned long long skip;

        if (!(ss >> rx_bytes)) {
            continue;
        }

        for (int i = 0; i < 7; i++) {
            if (!(ss >> skip)) {
                break;
            }
        }

        if (!(ss >> tx_bytes)) {
            continue;
        }

        rx_total += rx_bytes;
        tx_total += tx_bytes;
    }

    if ((rx_total == 0) && (tx_total == 0)) {
        return false;
    }

    *rx = rx_total;
    *tx = tx_total;
    return true;
}

void G13::format_speed(unsigned long long bytes_per_sec, string *out) {
    if (bytes_per_sec >= (1024ULL * 1024ULL * 1024ULL)) {
        double gb = ((double)bytes_per_sec) / (1024.0 * 1024.0 * 1024.0);
        char buf[32];
        sprintf(buf, "%4.1fGB/s", gb);
        *out = buf;
    }
    else if (bytes_per_sec >= (1024ULL * 1024ULL)) {
        double mb = ((double)bytes_per_sec) / (1024.0 * 1024.0);
        char buf[32];
        sprintf(buf, "%4.1fMB/s", mb);
        *out = buf;
    }
    else if (bytes_per_sec >= 1024ULL) {
        double kb = ((double)bytes_per_sec) / 1024.0;
        char buf[32];
        sprintf(buf, "%4.1fKB/s", kb);
        *out = buf;
    }
    else {
        char buf[32];
        sprintf(buf, "%4lluB/s", (unsigned long long)bytes_per_sec);
        *out = buf;
    }
}

void G13::render_stats_to_lcd() {
    double sample_time = chrono::duration<double>(chrono::steady_clock::now().time_since_epoch()).count();
    if (last_stats_sample >= 0 && sample_time - last_stats_sample < stats_poll_seconds && !stats_lines.empty()) {
        write_lines_to_lcd(stats_lines);
        return;
    }
    last_stats_sample = sample_time;
    auto average = [&](const string &name, double value) {
        return stats_average.add(name, value, sample_time, stats_average_seconds);
    };
    int cpu_percent = -1;
    int mem_percent = -1;
    int disk_percent = -1;
    int cpu_temperature = -1;
    int network_temperature = -1;
    int root_temperature = -1;

    unsigned long long total = 0;
    unsigned long long idle = 0;
    if (read_cpu_sample(&total, &idle)) {
        if (this->has_prev_cpu && (total > this->prev_cpu_total) && (idle >= this->prev_cpu_idle)) {
            unsigned long long d_total = total - this->prev_cpu_total;
            unsigned long long d_idle = idle - this->prev_cpu_idle;
            if (d_total > 0) {
                cpu_percent = (int)(((d_total - d_idle) * 100ULL) / d_total);
            }
        }

        this->prev_cpu_total = total;
        this->prev_cpu_idle = idle;
        this->has_prev_cpu = true;
    }

    int active_threads = read_active_threads();
    int psu_watts = read_psu_watts();
    read_mem_percent(&mem_percent);
    read_cpu_temperature(&cpu_temperature);
    read_network_temperature(&network_temperature);
    read_root_temperature(&root_temperature);

    string gpu_text;
    bool has_gpu = read_gpu_line(&gpu_text, sample_time);
    if (!has_gpu) { average("gpu", -1); average("vram", -1); average("gpu_temp", -1); }

    string net_speed_text = "n/a";
    double net_rate = -1;
    unsigned long long rx = 0;
    unsigned long long tx = 0;
    if (read_net_sample(&rx, &tx)) {
        time_t now = time(NULL);
        if (this->has_prev_net && (now > this->prev_net_seconds)) {
            unsigned long long d_seconds = now - this->prev_net_seconds;
            if (d_seconds > 0) {
                unsigned long long d_rx = (rx > this->prev_net_rx) ? (rx - this->prev_net_rx) : 0;
                unsigned long long d_tx = (tx > this->prev_net_tx) ? (tx - this->prev_net_tx) : 0;
                unsigned long long total_per_sec = (d_rx + d_tx) / d_seconds;
                net_rate = total_per_sec;
            }
        }

        this->prev_net_rx = rx;
        this->prev_net_tx = tx;
        this->prev_net_seconds = now;
        this->has_prev_net = true;
    }

    unsigned long long disk_read_per_sec = 0;
    unsigned long long disk_write_per_sec = 0;
    bool disk_baseline = has_prev_disk;
    bool disk_ok = read_disk_io_speed(&disk_read_per_sec, &disk_write_per_sec);
    read_disk_percent(&disk_percent);

    cpu_percent = lround(average("cpu", cpu_percent));
    active_threads = lround(average("threads", active_threads));
    mem_percent = lround(average("ram", mem_percent));
    disk_percent = lround(average("root", disk_percent));
    cpu_temperature = lround(average("cpu_temp", cpu_temperature));
    network_temperature = lround(average("nic_temp", network_temperature));
    root_temperature = lround(average("root_temp", root_temperature));
    psu_watts = lround(average("psu", psu_watts));
    net_rate = average("network", net_rate);
    if (net_rate >= 0) format_speed(static_cast<unsigned long long>(net_rate), &net_speed_text);
    double read_rate = average("read", disk_ok && disk_baseline ? static_cast<double>(disk_read_per_sec) : -1);
    double write_rate = average("write", disk_ok && disk_baseline ? static_cast<double>(disk_write_per_sec) : -1);
    string disk_speed = "n/a";
    double rate = stats_show_write ? write_rate : read_rate;
    if (rate >= 0) format_speed(static_cast<unsigned long long>(rate), &disk_speed);

    string cpu_line = "CPU " + (cpu_percent >= 0 ? to_string(cpu_percent) + "%" : "n/a")
            + " THR " + (active_threads >= 0 ? to_string(active_threads) : "n/a")
            + " " + (cpu_temperature >= 0 ? to_string(cpu_temperature) + "C" : "n/a");


    string memory_line = "MEM " + (mem_percent >= 0 ? to_string(mem_percent) + "%" : "n/a")
            + " PSU " + (psu_watts >= 0 ? to_string(psu_watts) + "W" : "n/a");


    if (!has_gpu) gpu_text = "GPU n/a";
    string network_line = "NET " + net_speed_text + " NIC "
            + (network_temperature >= 0 ? to_string(network_temperature) + "C" : "n/a");
    string root_line = "ROOT " + (disk_percent >= 0 ? to_string(disk_percent) + "%" : "n/a")
            + " " + (root_temperature >= 0 ? to_string(root_temperature) + "C" : "n/a")
            + (stats_show_write ? " W" : " R") + disk_speed;
    stats_show_write = !stats_show_write;
    stats_lines = {cpu_line, memory_line, gpu_text, network_line, root_line};
    write_lines_to_lcd(stats_lines);
}
int G13::read() {
    unsigned char buffer[G13_REPORT_SIZE];
    int size;
    int error = libusb_interrupt_transfer(handle, LIBUSB_ENDPOINT_IN | G13_KEY_ENDPOINT, buffer, G13_REPORT_SIZE, &size, brightness_held ? 25 : 1000);
    if (error && error != LIBUSB_ERROR_TIMEOUT) {
        std::map<int, std::string> errors;
        errors[LIBUSB_SUCCESS] = "LIBUSB_SUCCESS";
        errors[LIBUSB_ERROR_IO] = "LIBUSB_ERROR_IO";
        errors[LIBUSB_ERROR_INVALID_PARAM] = "LIBUSB_ERROR_INVALID_PARAM";
        errors[LIBUSB_ERROR_ACCESS] = "LIBUSB_ERROR_ACCESS";
        errors[LIBUSB_ERROR_NO_DEVICE] = "LIBUSB_ERROR_NO_DEVICE";
        errors[LIBUSB_ERROR_NOT_FOUND] = "LIBUSB_ERROR_NOT_FOUND";
        errors[LIBUSB_ERROR_BUSY] = "LIBUSB_ERROR_BUSY";
        errors[LIBUSB_ERROR_TIMEOUT] = "LIBUSB_ERROR_TIMEOUT";
        errors[LIBUSB_ERROR_OVERFLOW] = "LIBUSB_ERROR_OVERFLOW";
        errors[LIBUSB_ERROR_PIPE] = "LIBUSB_ERROR_PIPE";
        errors[LIBUSB_ERROR_INTERRUPTED] = "LIBUSB_ERROR_INTERRUPTED";
        errors[LIBUSB_ERROR_NO_MEM] = "LIBUSB_ERROR_NO_MEM";
        errors[LIBUSB_ERROR_NOT_SUPPORTED] = "LIBUSB_ERROR_NOT_SUPPORTED";
        errors[LIBUSB_ERROR_OTHER] = "LIBUSB_ERROR_OTHER    ";
        cerr << "Error while reading keys: " << error << " (" << errors[error]
                << ")" << endl;
        cerr << "Stopping daemon" << endl;
        return -1;
    }

    if (size == G13_REPORT_SIZE) {
        parse_joystick(buffer);
        parse_keys(buffer);
        send_event(EV_SYN, SYN_REPORT, 0);
    }
    return 0;
}

void G13::parse_joystick(unsigned char *buf) {
    int stick_x = buf[1];
    int stick_y = buf[2];

    //cout << "stick = (" << stick_x << ", " << stick_y << ")\n";


    if (stick_mode == STICK_ABSOLUTE) {
        send_event(EV_ABS, ABS_X, stick_x);
        send_event(EV_ABS, ABS_Y, stick_y);
    } else if (stick_mode == STICK_KEYS) {

        // 36=up, 37=left, 38=right, 39=down
        int pressed[4];

        if (stick_y <= 96) {
            pressed[0] = 1;
            pressed[3] = 0;
        }
        else if (stick_y >= 160) {
            pressed[0] = 0;
            pressed[3] = 1;
        }
        else {
            pressed[0] = 0;
            pressed[3] = 0;
        }

        if (stick_x <= 96) {
            pressed[1] = 1;
            pressed[2] = 0;
        }
        else if (stick_x >= 160) {
            pressed[1] = 0;
            pressed[2] = 1;
        }
        else {
            pressed[1] = 0;
            pressed[2] = 0;
        }


        int codes[4] = {36, 37, 38, 39};
        for (int i = 0; i < 4; i++) {
            int key = codes[i];
            int p = pressed[i];
            if (actions[key]->set(p)) {
                //cout << "key " << key << ", pressed=" << p << ", actions[key]->isPressed()="
                //      << actions[key]->isPressed() <<  ", x=" << stick_x << "\n";
            }
        }
    } else {
        /*    send_event(g13->uinput_file, EV_REL, REL_X, stick_x/16 - 8);
         send_event(g13->uinput_file, EV_REL, REL_Y, stick_y/16 - 8);*/
    }

}
void G13::parse_key(int key, unsigned char *byte) {
    unsigned char actual_byte = byte[key / 8];
    unsigned char mask = 1 << (key % 8);

    int pressed = actual_byte & mask;

    if (mode_profiles && key == G13_KEY_BD) {
        double now = chrono::duration<double>(chrono::steady_clock::now().time_since_epoch()).count();
        if (pressed && !brightness_held) {
            brightness_held = true;
            brightness_started = brightness_updated = now;
            brightness_direction = brightness >= 100 ? -1 : 1;
        } else if (!pressed && brightness_held) {
            update_brightness(now);
            brightness_held = false;
            save_brightness();
        }
        return;
    }
    // Mode selectors change bindings; independent LCD selectors change pages.
    if (this->mode_profiles && key >= 25 && key <= 32) {
        const int slot = key - 25;
        const bool down = pressed != 0;
        const bool rising = down && !this->mode_key_down[slot];
        this->mode_key_down[slot] = down;
        if (rising) {
            if (mode_screens && key < 29) {
                set_logiframe_page(key - 25);
            } else {
                const int next = key >= 29 ? key - 29 : key - 25;
                this->bindings = next;
                loadBindings();
            }
        }
        return;
    }

    switch (key) {
	case 25: // key 25-28 now switch LogiFrame pages 1-4
	case 26:
	case 27:
	case 28:
		if (pressed) {
			if (this->lcd_source == LCD_SOURCE_LOGIFRAME) {
				set_logiframe_page(key - 25);
			}
			else {
				// profile switch when not in LogiFrame mode
				bindings = key - 25;
				loadBindings();
			}
		}
		return;
        break;

    case 36: // key 36-39 are mapped as joystick keys
    case 37:
    case 38:
    case 39:
        return;
    }


    actions[key]->set(pressed);

    /*
    if (changed) {
        string type = "released";
        if (actions[key]->isPressed()) {
            type = "pressed";
        }
        cout << "G" << (key+1) << " " << type << "\n";
    }
    */
}
void G13::parse_keys(unsigned char *buf) {

    parse_key(G13_KEY_G1, buf + 3);
    parse_key(G13_KEY_G2, buf + 3);
    parse_key(G13_KEY_G3, buf + 3);
    parse_key(G13_KEY_G4, buf + 3);
    parse_key(G13_KEY_G5, buf + 3);
    parse_key(G13_KEY_G6, buf + 3);
    parse_key(G13_KEY_G7, buf + 3);
    parse_key(G13_KEY_G8, buf + 3);

    parse_key(G13_KEY_G9, buf + 3);
    parse_key(G13_KEY_G10, buf + 3);
    parse_key(G13_KEY_G11, buf + 3);
    parse_key(G13_KEY_G12, buf + 3);
    parse_key(G13_KEY_G13, buf + 3);
    parse_key(G13_KEY_G14, buf + 3);
    parse_key(G13_KEY_G15, buf + 3);
    parse_key(G13_KEY_G16, buf + 3);

    parse_key(G13_KEY_G17, buf + 3);
    parse_key(G13_KEY_G18, buf + 3);
    parse_key(G13_KEY_G19, buf + 3);
    parse_key(G13_KEY_G20, buf + 3);
    parse_key(G13_KEY_G21, buf + 3);
    parse_key(G13_KEY_G22, buf + 3);
    //  parse_key(G13_KEY_LIGHT_STATE, buf+3);

    parse_key(G13_KEY_BD, buf + 3);
    parse_key(G13_KEY_L1, buf + 3);
    parse_key(G13_KEY_L2, buf + 3);
    parse_key(G13_KEY_L3, buf + 3);
    parse_key(G13_KEY_L4, buf + 3);
    parse_key(G13_KEY_M1, buf + 3);
    parse_key(G13_KEY_M2, buf + 3);

    parse_key(G13_KEY_M3, buf + 3);
    parse_key(G13_KEY_MR, buf + 3);
    parse_key(G13_KEY_LEFT, buf + 3);
    parse_key(G13_KEY_DOWN, buf + 3);
    parse_key(G13_KEY_TOP, buf + 3);
    parse_key(G13_KEY_LIGHT, buf + 3);
    //  parse_key(G13_KEY_LIGHT2, buf+3, file);
    /*  cout << hex << setw(2) << setfill('0') << (int)buf[7];
     cout << hex << setw(2) << setfill('0') << (int)buf[6];
     cout << hex << setw(2) << setfill('0') << (int)buf[5];
     cout << hex << setw(2) << setfill('0') << (int)buf[4];
     cout << hex << setw(2) << setfill('0') << (int)buf[3] << endl;*/
}
