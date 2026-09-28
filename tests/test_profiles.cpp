#include <string>
#include <vector>
#include <map>
#include <cstdint>
#include <csignal>
#include <ctime>
#include <cassert>
#include <algorithm>
#include <iostream>
#include <fstream>
#include <cstdlib>
#include <cstring>
#include <sys/stat.h>
#define private public
#include "G13.h"
#undef private
#include "PassThroughAction.h"
#include "Font.h"
#include "StatsRate.h"
volatile sig_atomic_t g13_keep_running = 1;
static bool simulate_clock_step = false;
static time_t simulated_wall_time = 36000, wall_clock_step = -3600;
static int wall_clock_reads = 0;
static int input_polls = 0, lcd_writes = 0, initial_lcd_writes = 0;
static std::vector<char> usb_events;
extern "C" time_t __real_time(time_t *);
extern "C" time_t __wrap_time(time_t *result) {
    ++wall_clock_reads;
    if (!simulate_clock_step) return __real_time(result);
    if (result) *result = simulated_wall_time;
    return simulated_wall_time;
}
extern "C" int __wrap_libusb_open(libusb_device *, libusb_device_handle **) { return -1; }
extern "C" int __wrap_libusb_control_transfer(libusb_device_handle *, uint8_t, uint8_t, uint16_t value, uint16_t, unsigned char *, uint16_t length, unsigned int) {
    if (value == 0x307) usb_events.push_back('C');
    return length;
}
extern "C" int __wrap_libusb_interrupt_transfer(libusb_device_handle *, unsigned char endpoint, unsigned char *data, int length, int *actual, unsigned int) {
    if (endpoint == G13_LCD_ENDPOINT) {
        ++lcd_writes;
        bool blank = true;
        for (int i = 32; i < length; ++i) blank = blank && data[i] == 0;
        usb_events.push_back(blank ? 'B' : 'F');
    }
    if (simulate_clock_step && (endpoint & LIBUSB_ENDPOINT_IN)) {
        if (++input_polls == 1) {
            initial_lcd_writes = lcd_writes;
            simulated_wall_time += wall_clock_step; // NTP/manual correction.
        }
        usleep(1100000); // Real monotonic time advances through a USB timeout.
        *actual = 0;
        if (input_polls == 2) g13_keep_running = 0;
        return LIBUSB_ERROR_TIMEOUT;
    }
    *actual=length;
    return 0;
}
class ReleaseProbe : public G13Action {
    bool *released;
public:
    ReleaseProbe(bool *r): released(r) {}
    void key_up() { *released=true; }
};
int main() {
    char directory[] = "/tmp/g13-profile-test-XXXXXX";
    assert(mkdtemp(directory));
    setenv("HOME",directory,1);
    std::string base = std::string(directory)+"/.g13";
    mkdir(base.c_str(),0700);
    for(int i=0;i<4;i++) {
        std::ofstream out((base+"/bindings-"+std::to_string(i)+".properties").c_str());
        out << "# regression: read beyond the first property\nmode_profiles=1\nlcd_mode=logiframe\n";
        out << "lcd_logiframe_page2_cmd=printf test\nlcd_logiframe_page3_cmd=printf test\nlcd_logiframe_page4_cmd=printf test\n";
        out << "G33=p,k.57\nG34=p,k.28\nG36=p,k.17\nG37=p,k.30\nG38=p,k.32\nG39=p,k.31\n";
        out << "#" << std::string(4096,'x') << "\n";
        out << "G0=p,k." << 16+i << "\nlcd_logiframe_page4_color=1,2,3\n";
    }
    G13 driver(NULL); // USB open is stubbed; no hardware touched.
    // Exercise NVIDIA CSV parsing without querying the host GPU.
    std::string original_path = getenv("PATH") ? getenv("PATH") : "";
    std::string fake_smi = std::string(directory) + "/nvidia-smi";
    setenv("PATH", directory, 1);
    const char *samples[] = {"19, 3736, 16303, 56", "100, 8000, 8000, 100",
                            "[N/A], 100, 400, 45", "0, 0, 0, [N/A]",
                            "5, [N/A], 8000, 60"};
    const char *expected[] = {"GPU 19% MEM 23% 56C", "GPU 100% MEM 100% 100C",
                             "GPU n/a MEM 25% 45C", "GPU 0% MEM n/a n/a",
                             "GPU 5% MEM n/a 60C"};
    for (int i = 0; i < 5; i++) {
        std::ofstream script(fake_smi.c_str());
        script << "#!/bin/sh\nprintf '%s\\n' '" << samples[i] << "'\n";
        script.close();
        chmod(fake_smi.c_str(), 0700);
        std::string line;
        assert(driver.read_gpu_line(&line));
        assert(line == expected[i]);
        assert(line.size() <= 26);
    }
    setenv("PATH", original_path.c_str(), 1);
    std::string stat_path = std::string(directory) + "/stat";
    auto cpu_sample = [&](const char *text) {
        std::ofstream sample(stat_path.c_str());
        sample << text;
        sample.close();
        return driver.read_active_threads(stat_path);
    };
    assert(cpu_sample("cpu0 0 0 0 100 0 0 0 0\ncpu1 0 0 0 100 0 0 0 0\n") == -1);
    // Exactly 5% is below the activity threshold; guest fields are not counted twice.
    assert(cpu_sample("cpu0 5 0 0 195 0 0 0 0 90 0\ncpu1 6 0 0 194 0 0 0 0\n") == 1);
    assert(cpu_sample("cpu0 5 0 0 295 0 0 0 0\ncpu1 6 0 0 294 0 0 0 0\n") == 0);
    // A new/hot-plugged thread needs its own baseline; removed threads are forgotten.
    assert(cpu_sample("cpu2 50 0 0 50 0 0 0 0\n") == -1);
    assert(cpu_sample("cpu2 60 0 0 140 0 0 0 0\n") == 1);
    assert(cpu_sample("cpu2 0 0 0 1 0 0 0 0\n") == -1);
    assert(driver.read_active_threads(stat_path + ".missing") == -1);

    std::string hwmon = std::string(directory) + "/hwmon0";
    mkdir(hwmon.c_str(), 0700);
    std::ofstream(hwmon + "/name") << "corsairpsu\n";
    std::ofstream(hwmon + "/power1_label") << "power +12v\n";
    std::ofstream(hwmon + "/power1_input") << "226000000\n";
    std::ofstream(hwmon + "/power2_label") << "power total\n";
    std::ofstream(hwmon + "/power2_input") << "282600000\n";
    assert(driver.read_psu_watts(directory) == 283);
    std::ofstream(hwmon + "/power2_input") << "0\n";
    assert(driver.read_psu_watts(directory) == 0);
    std::ofstream(hwmon + "/power2_input") << "unavailable\n";
    assert(driver.read_psu_watts(directory) == -1);
    assert(driver.read_psu_watts(std::string(directory) + "/missing") == -1);

    StatsAverage averages;
    assert(averages.add("cpu", 10, 0, 5) == 10);
    assert(averages.add("cpu", 30, 1, 5) == 20);
    assert(averages.add("cpu", 50, 5, 5) == 40); // t=0 expired
    assert(averages.add("cpu", 70, 11, 5) == 70); // gaps expire old data
    assert(averages.add("cpu", -1, 12, 5) == -1); // unavailable is not zero
    assert(averages.add("cpu", 20, 13, 5) == 20);
    assert(averages.add("disk", 100, 13, 5) == 100); // independent metrics
    assert(averages.add("cpu", 40, 13, 5) == 40); // replace duplicate timestamp
    averages.clear();
    assert(averages.add("cpu", 80, 14, 5) == 80);

    // Rates use fractional monotonic intervals and tolerate counter resets.
    assert(bytes_per_second(1500, 500, 1.0) == 1000);
    assert(bytes_per_second(1500, 500, 1.25) == 800);
    assert(bytes_per_second(1500, 500, 0.5) == 2000);
    assert(bytes_per_second(500, 1500, 1.0) == 0);
    assert(bytes_per_second(1500, 500, 0.0) == 0);
    assert(bytes_per_second(1500, 500, -1.0) == 0);
    assert(bytes_per_second(1500, 500, INFINITY) == 0);
    assert(bytes_per_second(1500, 500, NAN) == 0);

    // Render both disk directions, and verify polling reuses the current frame.
    wall_clock_reads = 0;
    setenv("PATH", directory, 1);
    driver.render_stats_to_lcd();
    assert(driver.stats_lines.size() == 5);
    assert(driver.stats_lines[4].find(" R") != std::string::npos);
    auto cached_lines = driver.stats_lines;
    driver.render_stats_to_lcd();
    assert(driver.stats_lines == cached_lines);
    driver.last_stats_sample -= 2;
    driver.render_stats_to_lcd();
    assert(driver.stats_lines[4].find(" W") != std::string::npos);
    assert(driver.stats_lines[4].find(" R") == std::string::npos);
    assert(driver.stats_lines[4].size() <= 26);
    setenv("PATH", original_path.c_str(), 1);

    assert(wall_clock_reads == 0); // No wall-clock dependency in stats/rates.

    // Lowercase must not shift when a backslash comment is preprocessed.
    assert(sizeof(font_5x7) == 475);
    driver.clear_lcd_buffer();
    driver.write_char(0, 0, 'a');
    const unsigned char expected_a[] = {0x20,0x54,0x54,0x54,0x78};
    assert(memcmp(driver.lcd_buffer, expected_a, 5) == 0);
    driver.clear_lcd_buffer();
    driver.write_char(0, 0, char(127));
    for (int i=0;i<5;i++) assert(driver.lcd_buffer[i] == 0);
    driver.write_lines_to_lcd(std::vector<std::string>(5, "Steam Codex Discord"));
    driver.write_lines_to_lcd(std::vector<std::string>(1, "a"));
    assert(memcmp(driver.lcd_buffer, expected_a, 5) == 0);
    for (int i=5;i<G13_LCD_BUFFER_SIZE;i++) assert(driver.lcd_buffer[i] == 0);
    driver.loadBindings();
    assert(driver.mode_profiles);
    unsigned char stick_report[8]={0};
    stick_report[1]=0;stick_report[2]=0;
    driver.parse_joystick(stick_report);
    assert(driver.actions[36]->isPressed() && driver.actions[37]->isPressed());
    assert(!driver.actions[38]->isPressed() && !driver.actions[39]->isPressed());
    stick_report[1]=255;stick_report[2]=255;
    driver.parse_joystick(stick_report);
    assert(!driver.actions[36]->isPressed() && !driver.actions[37]->isPressed());
    assert(driver.actions[38]->isPressed() && driver.actions[39]->isPressed());
    stick_report[1]=128;stick_report[2]=128;driver.parse_joystick(stick_report);
    for(int i=36;i<=39;i++) assert(!driver.actions[i]->isPressed());
    unsigned char thumb_report[5]={0};thumb_report[4]=(1<<1)|(1<<2);
    driver.parse_key(33,thumb_report);driver.parse_key(34,thumb_report);
    assert(driver.actions[33]->isPressed() && driver.actions[34]->isPressed());
    thumb_report[4]=0;driver.parse_key(33,thumb_report);driver.parse_key(34,thumb_report);
    assert(!driver.actions[33]->isPressed() && !driver.actions[34]->isPressed());

    assert(driver.logiframe_page_colors[3][2] == 3);
    assert(dynamic_cast<PassThroughAction*>(driver.actions[0])->getKeyCode()==16);
    bool released=false;
    delete driver.actions[1];
    driver.actions[1]=new ReleaseProbe(&released);
    driver.actions[1]->set(1);
    unsigned char report[5]={0};
    report[30/8] |= 1 << (30%8); // Physical M2
    driver.parse_key(30,report);
    assert(released);
    assert(driver.bindings==1 && driver.logiframe_page==1);
    assert(dynamic_cast<PassThroughAction*>(driver.actions[0])->getKeyCode()==17);
    G13Action *action=driver.actions[0];
    driver.actions[0]->set(1);
    driver.parse_key(30,report); // Held selector must not reload.
    assert(driver.actions[0]==action && driver.actions[0]->isPressed());
    memset(report,0,sizeof(report)); driver.parse_key(30,report);
    report[32/8] |= 1 << (32%8); driver.parse_key(32,report);
    assert(driver.bindings==3 && driver.logiframe_page==3);
    memset(report,0,sizeof(report)); driver.parse_key(32,report);
    report[29/8] |= 1 << (29%8); driver.parse_key(29,report);
    assert(driver.bindings==0 && driver.logiframe_page==0);
    for (int i = 0; i < 4; i++) {
        std::ofstream extra(base + "/bindings-" + std::to_string(i) + ".properties", std::ios::app);
        extra << "mode_screens=1\nlcd_logiframe_page1_stats=0\nlcd_logiframe_page4_stats=1\n";
    }
    driver.loadBindings();
    assert(driver.mode_screens && !driver.page_stats[0] && driver.page_stats[3]);
    memset(report, 0, sizeof(report)); driver.parse_key(29, report);
    report[26/8] |= 1 << (26%8); // L2 changes screen only.
    action = driver.actions[0];
    driver.parse_key(26, report);
    assert(driver.bindings == 0 && driver.logiframe_page == 1 && driver.actions[0] == action);
    memset(report, 0, sizeof(report)); driver.parse_key(26, report);
    report[30/8] |= 1 << (30%8); driver.parse_key(30, report);
    assert(driver.bindings == 1 && driver.logiframe_page == 0);
    memset(report, 0, sizeof(report)); driver.parse_key(30, report);
    report[29/8] |= 1 << (29%8); driver.parse_key(29, report);
    assert(driver.bindings == 0 && driver.logiframe_page == 1); // Recall each mode's screen.

    driver.brightness = 50;
    driver.brightness_held = true;
    driver.brightness_started = driver.brightness_updated = 0;
    driver.brightness_direction = 1;
    driver.update_brightness(0.2); assert(std::abs(driver.brightness - 50) < 0.0001); // Ignore short taps.
    driver.update_brightness(2.9); assert(std::abs(driver.brightness - 100) < 0.0001);
    driver.update_brightness(5.4); assert(std::abs(driver.brightness - 50) < 0.0001);
    driver.update_brightness(7.9); assert(std::abs(driver.brightness - 0) < 0.0001);
    driver.update_brightness(10.4); assert(std::abs(driver.brightness - 50) < 0.0001);
    driver.brightness_held = false;
    driver.update_brightness(12.9); assert(std::abs(driver.brightness - 50) < 0.0001);
    driver.save_brightness();
    double brightness_saved = -1;
    std::ifstream(base + "/brightness") >> brightness_saved;
    assert(brightness_saved == 50);

    // Forward AND backward wall-clock corrections must not suspend LCD writes.
    // Page 1 is plain text here: no real GPU/DDC devices are queried.
    for (time_t step : {-3600, 3600}) {
        driver.bindings = 0;
        driver.selected_pages[0] = 0;
        driver.handle = NULL;
        driver.loaded = 1;
        input_polls = 0;
        wall_clock_step = step;
        simulated_wall_time = 36000;
        simulate_clock_step = true;
        driver.start();
        simulate_clock_step = false;
        driver.loaded = 0; // Keep the destructor away from a real USB handle.
        g13_keep_running = 1;
        assert(input_polls == 2);
        assert(lcd_writes == initial_lcd_writes + 2);
    }

    // Real child processes, mocked USB: a slow page cannot block a mode switch.
    std::string marker = std::string(directory) + "/late-result";
    std::ofstream(base + "/bindings-1.properties")
        << "mode_profiles=1\nmode_screens=1\nlcd_mode=logiframe\n"
        << "color=20,30,40\nlcd_logiframe_page1_stats=0\n"
        << "lcd_logiframe_page1_cmd=/bin/sleep 0.5; printf old > " << marker << "\n";
    driver.loaded = 1;
    driver.bindings = 1;
    memset(driver.lcd_buffer, 0xff, sizeof(driver.lcd_buffer));
    usb_events.clear();
    auto started = std::chrono::steady_clock::now();
    driver.loadBindings();
    auto transition_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - started).count();
    assert(transition_ms < 250);
    assert(driver.last_stats_sample == -1); // No partially parsed statistics page.
    assert(!usb_events.empty() && usb_events.front() == 'B');
    assert(driver.lcd_command.running());
    for (char event : usb_events) assert(event != 'F'); // Only blanks before data.
    assert(std::find(usb_events.begin(), usb_events.end(), 'C') != usb_events.end());
    driver.bindings = 2;
    driver.loadBindings();
    assert(!driver.lcd_command.running());
    usleep(600000);
    driver.poll_lcd_command();
    assert(access(marker.c_str(), F_OK) != 0); // Cancelled descendants cannot finish.

    auto finish_page = [&]() {
        auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
        while (driver.lcd_command.running() && std::chrono::steady_clock::now() < deadline) {
            driver.poll_lcd_command();
            usleep(1000);
        }
        assert(!driver.lcd_command.running());
    };
    driver.logiframe_page_cmds[0] = "printf cached";
    driver.set_logiframe_page(0);
    finish_page();
    assert(driver.lcd_command.succeeded);
    std::string cached_frame(reinterpret_cast<char *>(driver.lcd_buffer), G13_LCD_BUFFER_SIZE);
    driver.logiframe_page_cmds[1] = "/bin/sleep 5; printf obsolete";
    driver.set_logiframe_page(1);
    started = std::chrono::steady_clock::now();
    driver.set_logiframe_page(0);
    assert(std::chrono::steady_clock::now() - started < std::chrono::milliseconds(250));
    assert(std::string(reinterpret_cast<char *>(driver.lcd_buffer), G13_LCD_BUFFER_SIZE) == cached_frame);
    driver.logiframe_page_cmds[0] = "/bin/sleep 5; printf changed";
    driver.set_logiframe_page(0);
    for (unsigned char pixel : driver.lcd_buffer) assert(pixel == 0); // Invalidate stale cache.
    driver.lcd_command.cancel();
    std::string pbm_file = std::string(directory) + "/page.pbm";
    {
        std::ofstream pbm(pbm_file);
        pbm << "P1\n160 43\n1 ";
        for (int pixel = 1; pixel < 160 * 43; ++pixel) pbm << "0 ";
    }
    driver.logiframe_page_cmds[0] = "cat " + pbm_file;
    driver.set_logiframe_page(0);
    finish_page();
    assert(driver.lcd_command.succeeded);
    assert(driver.lcd_buffer[0] == 1);
    for (int pixel = 1; pixel < G13_LCD_BUFFER_SIZE; ++pixel) assert(driver.lcd_buffer[pixel] == 0);
    driver.loaded = 0;

    LcdCommand command;
    auto finish_command = [&]() {
        auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(2);
        while (command.running() && std::chrono::steady_clock::now() < deadline) {
            command.poll();
            usleep(1000);
        }
        assert(!command.running());
    };
    assert(command.start("/bin/sleep 5", 50));
    finish_command(); assert(!command.succeeded); // A wedged provider is bounded.
    assert(command.start("printf failed; exit 7"));
    finish_command(); assert(!command.succeeded);
    assert(command.start("head -c 70000 /dev/zero"));
    finish_command(); assert(!command.succeeded); // Bound memory/output too.
    std::string count_file = std::string(directory) + "/command-count";
    assert(command.start("printf x >> " + count_file));
    finish_command(); assert(command.succeeded && command.output.empty());
    std::ifstream count_stream(count_file);
    std::string count; count_stream >> count;
    assert(count == "x"); // Empty output does not invoke a fallback command again.
    std::cout << "Slow-page mode transition: " << transition_ms << " ms; cache/cancellation/timeout checks passed\n";

    for(int i=0;i<4;i++) std::remove((base+"/bindings-"+std::to_string(i)+".properties").c_str());
    rmdir(base.c_str());rmdir(directory);
}
