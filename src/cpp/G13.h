#ifndef __G13_H__
#define __G13_H__

#include <string>
#include <cstdint>
#include <csignal>
#include <ctime>
#include <map>
#include <libusb-1.0/libusb.h>
#include <vector>

#include "Constants.h"
#include "StatsAverage.h"
#include "G13Action.h"
#include "Macro.h"

using namespace std;

// Cleared by the SIGINT/SIGTERM handler in Main.cpp so worker loops can unwind.
extern volatile sig_atomic_t g13_keep_running;

class G13 {
private:
    G13Action            *actions[G13_NUM_KEYS];

    libusb_device        *device;
    libusb_device_handle *handle;
    int                   uinput_file;
    int                   lcd_fifo_fd;
    string                lcd_fifo_path;
    string                fifo_remainder;
    string                fifo_lines[5];

    int                   loaded;
    int                   keepGoing;
    int                   lcd_source;
    bool                  has_lcd_cache;
    bool                  mode_profiles;
    bool                  mode_key_down[8];
    int                   logiframe_page;
    int                   logiframe_page_count;
    string                logiframe_page_cmds[4];
    int                   logiframe_default_color[3];
    int                   logiframe_page_colors[4][3];

    stick_mode_t          stick_mode;
    int                   stick_keys[4];

    int                   bindings;
    unsigned char         lcd_buffer[G13_LCD_BUFFER_SIZE];
    time_t                last_lcd_update;
    unsigned long long     prev_cpu_total;
    unsigned long long     prev_cpu_idle;
    unsigned long long     prev_net_rx;
    unsigned long long     prev_net_tx;
    unsigned long long     prev_disk_read_bytes;
    unsigned long long     prev_disk_write_bytes;
    int                   prev_net_seconds;
    int                   prev_disk_seconds;
    bool                  has_prev_cpu;
    bool                  has_prev_net;
    bool                  has_prev_disk;

    Macro *loadMacro(int id);
    void clear_lcd_buffer();
    void set_pixel(int x, int y, bool on);
    void write_lcd();
    void write_char(int x, int y, char c);
    void write_text(int x, int y, const std::string &text);

    bool read_cpu_sample(unsigned long long *total, unsigned long long *idle);
    int read_active_threads(const std::string &path = "/proc/stat");
    int read_psu_watts(const std::string &root = "/sys/class/hwmon");
    std::map<std::string, std::pair<unsigned long long, unsigned long long> > prev_threads;
    bool read_mem_percent(int *percent);
    bool read_gpu_line(std::string *text, double sample_time = -1);
    bool read_net_sample(unsigned long long *rx, unsigned long long *tx);
    bool read_disk_percent(int *percent);
    bool read_disk_io_bytes(unsigned long long *read_bytes, unsigned long long *write_bytes);
    bool read_disk_io_speed(unsigned long long *read_per_sec, unsigned long long *write_per_sec);
    void format_speed(unsigned long long bytes_per_sec, std::string *out);
    StatsAverage stats_average;
    int stats_poll_seconds = 1;
    int stats_average_seconds = 5;
    double last_stats_sample = -1;
    bool stats_show_write = false;
    std::vector<std::string> stats_lines;
    std::string format_gpu_line(long long usage, long long used, long long total, long long temperature, double sample_time);
    void render_stats_to_lcd();
    void set_logiframe_page_leds();
    void set_logiframe_page(int page);
    void render_logiframe_page();
    void apply_logiframe_page_color();
    bool render_logiframe_usage_page();
    bool render_logiframe_page_with_command(int index, const std::string &title);
    bool run_command_lines(const std::string &command, std::vector<std::string> *lines);
    bool run_command_raw(const std::string &command, std::string *output);
    bool render_logiframe_raw_pbm(const std::string &output);
    bool write_lines_to_lcd(const std::vector<std::string> &lines);
    bool setup_lcd_fifo(const std::string &path);
    void cache_fifo_lines(const std::string &text);
    bool render_fifo_to_lcd();
    bool render_lcd();
    void set_lcd_source(const std::string &mode, const std::string &path);

    int  read();
    void parse_joystick(unsigned char *buf);
    void parse_key(int key, unsigned char *byte);
    void parse_keys(unsigned char *buf);

public:
    G13(libusb_device *device);
    ~G13();

    void start();
    void stop();
    void loadBindings();
    void setModeLeds(int leds);
    void setColor(int r, int g, int b);
};


#endif
