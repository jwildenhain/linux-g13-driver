#ifndef __G13_H__
#define __G13_H__

#include <string>
#include <cstdint>
#include <ctime>
#include <map>

#include "Constants.h"
#include "G13Action.h"
#include "Macro.h"

using namespace std;

class G13 {
private:
	G13Action            *actions[G13_NUM_KEYS];

	libusb_device        *device;
	libusb_device_handle *handle;
	int                   uinput_file;

	int                   loaded;
	int                   keepGoing;

	stick_mode_t          stick_mode;
	int                   stick_keys[4];

	int                   bindings;
	unsigned char         lcd_buffer[G13_LCD_BUFFER_SIZE];
	time_t                last_lcd_update;
	unsigned long long     prev_cpu_total;
	unsigned long long     prev_cpu_idle;
	unsigned long long     prev_net_rx;
	unsigned long long     prev_net_tx;
	int                   prev_net_seconds;
	bool                  has_prev_cpu;
	bool                  has_prev_net;

	Macro *loadMacro(int id);
	void clear_lcd_buffer();
	void set_pixel(int x, int y, bool on);
	void write_lcd();
	void write_char(int x, int y, char c);
	void write_text(int x, int y, const std::string &text);

	bool read_cpu_sample(unsigned long long *total, unsigned long long *idle);
	bool read_mem_percent(int *percent);
	bool read_gpu_line(std::string *text);
	bool read_net_sample(unsigned long long *rx, unsigned long long *tx);
	bool read_disk_percent(int *percent);
	void format_speed(unsigned long long bytes_per_sec, std::string *out);
	void render_stats_to_lcd();

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
	void setColor(int r, int g, int b);
};


#endif
