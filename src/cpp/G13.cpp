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
#include <sys/statvfs.h>
#include <sstream>

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


G13::G13(libusb_device *device) {

    this->device = device;

    this->loaded = 0;

    this->bindings = 0;

    this->stick_mode = STICK_KEYS;
    this->last_lcd_update = 0;
    this->prev_cpu_total = 0;
    this->prev_cpu_idle = 0;
    this->prev_net_rx = 0;
    this->prev_net_tx = 0;
    this->prev_net_seconds = 0;
    this->has_prev_cpu = false;
    this->has_prev_net = false;

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
    }

    if (libusb_claim_interface(handle, 0) < 0) {
        cerr << "Cannot Claim Interface" << endl;
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

    libusb_release_interface(this->handle, 0);
    libusb_close(this->handle);

}

void G13::start() {
    if (!this->loaded) {
        return;
    }

    loadBindings();

    keepGoing = 1;
    render_stats_to_lcd();
    this->last_lcd_update = time(NULL);

    while (keepGoing) {
        read();
        time_t now = time(NULL);
        if ((now - this->last_lcd_update) >= 1) {
            render_stats_to_lcd();
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
    cout << "loading " << filename << "\n";      ifstream file (filename);
      if (!file.is_open()) {
          cout << "Could not open config file: " << filename << "\n";
          setColor(128, 128, 128);
          return;
      }


      while (file.good()) {
          string line;
          getline(file, line);

          char l[1024];
          strcpy(l, (char *)line.c_str());
          trim(l);
          if (strlen(l) > 0) {
              char *key = strtok(l, "=");
              if (key[0] == '#') {
                  // ignore line
              }
              else if (strcmp(key, "color") == 0) {
                  char *num = strtok(NULL, ",");
                  int r = atoi(num);
                  num = strtok(NULL, ",");
                  int g = atoi(num);
                  num = strtok(NULL, ",");
                  int b = atoi(num);

                  setColor(r, g, b);
              }
              else if (strcmp(key, "stick_mode") == 0) {

              }
              else if (key[0] == 'G') {
                  int gKey = atoi(&key[1]);
                  //cout << "gKey = " << gKey << "\n";
                  char *type = strtok(NULL, ",");
                  trim(type);
                  //cout << "type = " << type << "\n";
                  if (strcmp(type, "p") == 0) { /* passthrough */
                      char *keytype = strtok(NULL, ",\n ");
                      trim(keytype);
                      int keycode = atoi(&keytype[2]);

                      if (actions[gKey] != null) {
                          delete actions[gKey];
                      }

                      //cout << "assigning G" << gKey << " to keycode " << keycode << "\n";
                      G13Action *action = new PassThroughAction(keycode);
                      actions[gKey] = action;
                  }
                  else if (strcmp(type, "m") == 0) { /* macro */
                      int macroId = atoi(strtok(NULL, ",\n "));
                      int repeats = atoi(strtok(NULL, ",\n "));
                      //cout << "macroId = " << macroId << "\n";
                      Macro *macro = loadMacro(macroId);
                      MacroAction *action = new MacroAction(macro->getSequence());
                      action->setRepeats(repeats);
                      actions[gKey] = action;
                  }
                  else {
                      cout << "G13::loadBindings() unknown type '" << type << "\n";
                  }

              }
              else {
                  cout << "G13::loadBindings() Unknown first token: " << key << "\n";
              }
          }

          //cout << line << endl;
      }

      file.close();
}

void G13::setColor(int red, int green, int blue) {
    int error;
    unsigned char usb_data[] = { 5, 0, 0, 0, 0 };
    usb_data[1] = red;
    usb_data[2] = green;
    usb_data[3] = blue;

    error = libusb_control_transfer(handle, LIBUSB_REQUEST_TYPE_CLASS | LIBUSB_RECIPIENT_INTERFACE, 9, 0x307, 0,
            usb_data, 5, 1000);

    if (error != 5) {
        cerr << "Problem sending data" << endl;
    }

}

void G13::clear_lcd_buffer() {
    memset(this->lcd_buffer, 0, G13_LCD_BUFFER_SIZE);
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
    if (c < 32 || c > 127) {
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

bool G13::read_gpu_line(string *text) {
    const char *paths[] = {
        "/sys/class/drm/card0/device/gpu_busy_percent",
        "/sys/class/drm/card1/device/gpu_busy_percent",
        "/sys/class/drm/card2/device/gpu_busy_percent",
        null
    };

    for (int i = 0; paths[i] != null; i++) {
        ifstream file(paths[i]);
        if (!file.is_open()) {
            continue;
        }

        int value = -1;
        if ((file >> value) && (value >= 0)) {
            char buf[32];
            if (value > 100) {
                value = 100;
            }
            sprintf(buf, "GPU %3d%%", value);
            *text = buf;
            return true;
        }
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
        size_t start = iface.find_first_not_of(" \t");
        if (start == string::npos) {
            continue;
        }
        size_t end = iface.find_last_not_of(" \t");
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
    int cpu_percent = -1;
    int mem_percent = -1;
    int disk_percent = -1;

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

    read_mem_percent(&mem_percent);

    string gpu_text;
    bool has_gpu = read_gpu_line(&gpu_text);

    string net_speed_text = "n/a";
    unsigned long long rx = 0;
    unsigned long long tx = 0;
    if (read_net_sample(&rx, &tx)) {
        time_t now = time(NULL);
        if (this->has_prev_net && (now > this->prev_net_seconds)) {
            unsigned long long d_seconds = now - this->prev_net_seconds;
            unsigned long long d_rx = (rx > this->prev_net_rx) ? (rx - this->prev_net_rx) : 0;
            unsigned long long d_tx = (tx > this->prev_net_tx) ? (tx - this->prev_net_tx) : 0;
            unsigned long long total_per_sec = (d_rx + d_tx) / d_seconds;
            format_speed(total_per_sec, &net_speed_text);
        }

        this->prev_net_rx = rx;
        this->prev_net_tx = tx;
        this->prev_net_seconds = now;
        this->has_prev_net = true;
    }

    read_disk_percent(&disk_percent);

    clear_lcd_buffer();

    char line[80];

    if (cpu_percent >= 0) {
        sprintf(line, "CPU %3d%%", cpu_percent);
    }
    else {
        sprintf(line, "CPU  n/a");
    }
    write_text(0, 0, line);

    if (mem_percent >= 0) {
        sprintf(line, "MEM %3d%%", mem_percent);
    }
    else {
        sprintf(line, "MEM  n/a");
    }
    write_text(0, 8, line);

    if (has_gpu) {
        write_text(0, 16, gpu_text);
    }
    else {
        write_text(0, 16, "GPU  n/a");
    }

    sprintf(line, "NET %s", net_speed_text.c_str());
    write_text(0, 24, line);

    if (disk_percent >= 0) {
        sprintf(line, "DSK %3d%%", disk_percent);
    }
    else {
        sprintf(line, "DSK  n/a");
    }
    write_text(0, 32, line);

    write_lcd();
}

int G13::read() {
    unsigned char buffer[G13_REPORT_SIZE];
    int size;
    int error = libusb_interrupt_transfer(handle, LIBUSB_ENDPOINT_IN | G13_KEY_ENDPOINT, buffer, G13_REPORT_SIZE, &size, 1000);
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

    switch (key) {
    case 25: // key 25-28 are mapped to change bindings
    case 26:
    case 27:
    case 28:
        if (pressed) {
            //cout << "key " << key << "\n";
            bindings = key - 25;
            loadBindings();
        }
        return;

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
