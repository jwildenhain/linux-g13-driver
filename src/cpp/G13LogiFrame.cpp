#include <stdio.h>

#include <vector>
#include <sstream>

#include "G13.h"

using namespace std;

namespace {
static const int LOGIFRAME_MAX_LINES = 5;
static const int LOGIFRAME_MAX_CHAR = 26;

string truncate_lcd_line(const string &line) {
    if ((int)line.size() <= LOGIFRAME_MAX_CHAR) {
        return line;
    }
    return line.substr(0, LOGIFRAME_MAX_CHAR);
}

static void strip_cr(std::string *line) {
    if (line == null || line->empty()) {
        return;
    }

    if ((*line)[line->size() - 1] == '\r') {
        line->resize(line->size() - 1);
    }
}

} // namespace

void G13::set_logiframe_page_leds() {
    const int leds[4] = {1, 2, 4, 8};
    const int page = mode_screens && mode_profiles ? bindings : this->logiframe_page;
    const int max_page = this->logiframe_page_count - 1;

    if (max_page < 0) {
        setModeLeds(0);
        return;
    }

    if (page >= 0 && page < 4 && page <= max_page) {
        setModeLeds(leds[page]);
    }
    else {
        setModeLeds(leds[0]);
    }
}

void G13::set_logiframe_page(int page) {
    lcd_command.cancel();
    clear_lcd_buffer();
    write_lcd();
    if (this->logiframe_page_count <= 0) {
        this->logiframe_page_count = 4;
    }

    if (page < 0) {
        this->logiframe_page = 0;
    }
    else if (page >= this->logiframe_page_count) {
        this->logiframe_page = 0;
    }
    else {
        this->logiframe_page = page;
    }

    if (mode_screens && mode_profiles) selected_pages[bindings] = logiframe_page;
    set_logiframe_page_leds();
    apply_logiframe_page_color();
    if (!(mode_screens ? page_stats[logiframe_page] : logiframe_page == 0)
            && cached_commands[bindings][logiframe_page] == logiframe_page_cmds[logiframe_page]
            && !cached_outputs[bindings][logiframe_page].empty()) {
        draw_command_output(cached_outputs[bindings][logiframe_page]);
    }
    render_logiframe_page();
    last_lcd_update = chrono::steady_clock::now();
}

bool G13::write_lines_to_lcd(const vector<string> &lines) {
    clear_lcd_buffer();

    for (int i = 0; i < LOGIFRAME_MAX_LINES; i++) {
        if (i < (int)lines.size()) {
            write_text(0, i * 8, truncate_lcd_line(lines[i]));
        }
    }

    write_lcd();
    return true;
}

bool G13::render_logiframe_raw_pbm(const string &output) {
    string token;
    stringstream ss(output);

    if (!(ss >> token) || token != "P1") {
        return false;
    }

    int width = 0;
    int height = 0;

    while (ss >> token) {
        if (token == "#") {
            getline(ss, token);
            continue;
        }

        width = atoi(token.c_str());
        if (ss >> token) {
            height = atoi(token.c_str());
        }
        break;
    }

    if (width <= 0 || height <= 0) {
        return false;
    }

    if (width != 160 || height != 43) {
        return false;
    }

    clear_lcd_buffer();
    for (int i = 0; i < (width * height); i++) {
        if (!(ss >> token)) {
            return false;
        }

        if (token != "0" && token != "1") {
            bool parsed = false;
            for (size_t j = 0; j < token.size(); j++) {
                if ((token[j] == '0') || (token[j] == '1')) {
                    token = token.substr((int)j, 1);
                    parsed = true;
                    break;
                }
            }

            if (!parsed) {
                return false;
            }
        }

        if (token != "0" && token != "1") {
            return false;
        }

        if (token == "1") {
            int px = i % width;
            int py = i / width;
            set_pixel(px, py, true);
        }
    }

    write_lcd();
    return true;
}

bool G13::draw_command_output(const string &output) {
    if (output.empty()) return false;
    if (render_logiframe_raw_pbm(output)) return true;
    vector<string> lines;
    stringstream stream(output);
    string line;
    while (lines.size() < LOGIFRAME_MAX_LINES && getline(stream, line)) {
        strip_cr(&line);
        lines.push_back(truncate_lcd_line(line));
    }
    return write_lines_to_lcd(lines);
}

void G13::poll_lcd_command() {
    if (!lcd_command.poll()) return;
    // Transitions cancel the old process, so only the selected page can finish.
    if (lcd_command.succeeded && !lcd_command.output.empty()) {
        cached_commands[bindings][logiframe_page] = pending_command;
        cached_outputs[bindings][logiframe_page] = lcd_command.output;
        draw_command_output(lcd_command.output);
    } else {
        write_lines_to_lcd({pending_title, "Display command failed", "Retrying..."});
    }
    // Refresh intervals begin at completion: no back-to-back slow DDC queries.
    last_lcd_update = chrono::steady_clock::now();
}

bool G13::render_logiframe_page_with_command(int index, const string &title) {
    if (index < 0 || index >= 4) return false;
    if (lcd_command.running()) return true;
    const string &command = logiframe_page_cmds[index];
    if (command.empty()) return write_lines_to_lcd({title});
    pending_command = command;
    pending_title = title;
    if (!lcd_command.start(command)) {
        return write_lines_to_lcd({title, "Cannot start display cmd"});
    }
    return true;
}

bool G13::render_logiframe_usage_page() {
    render_stats_to_lcd();
    set_logiframe_page_leds();
    return true;
}

void G13::render_logiframe_page() {
    set_logiframe_page_leds();

    if (mode_screens) {
        if (page_stats[logiframe_page]) render_logiframe_usage_page();
        else render_logiframe_page_with_command(logiframe_page, "M" + to_string(bindings + 1) + " / L" + to_string(logiframe_page + 1));
        return;
    }
    if (this->logiframe_page == 0) {
        render_logiframe_usage_page();
        return;
    }

    if (this->logiframe_page == 1) {
        render_logiframe_page_with_command(1, "Steam Friends");
        return;
    }

    if (this->logiframe_page == 2) {
        render_logiframe_page_with_command(2, "Token Usage");
        return;
    }

    render_logiframe_page_with_command(this->logiframe_page, "LogiFrame Page");
}
