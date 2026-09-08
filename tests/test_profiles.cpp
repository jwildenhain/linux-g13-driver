#include <string>
#include <vector>
#include <map>
#include <cstdint>
#include <csignal>
#include <ctime>
#include <cassert>
#include <fstream>
#include <cstdlib>
#include <cstring>
#include <sys/stat.h>
#define private public
#include "G13.h"
#undef private
#include "PassThroughAction.h"
#include "Font.h"
volatile sig_atomic_t g13_keep_running = 1;
extern "C" int __wrap_libusb_open(libusb_device *, libusb_device_handle **) { return -1; }
extern "C" int __wrap_libusb_control_transfer(libusb_device_handle *, uint8_t, uint8_t, uint16_t, uint16_t, unsigned char *, uint16_t length, unsigned int) { return length; }
extern "C" int __wrap_libusb_interrupt_transfer(libusb_device_handle *, unsigned char, unsigned char *, int length, int *actual, unsigned int) { *actual=length; return 0; }
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

    // Render both disk directions, and verify polling reuses the current frame.
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
    for(int i=0;i<4;i++) std::remove((base+"/bindings-"+std::to_string(i)+".properties").c_str());
    rmdir(base.c_str());rmdir(directory);
}
