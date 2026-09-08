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
    render_logiframe_page();
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

bool G13::run_command_lines(const string &command, vector<string> *lines) {
    if (command.empty() || lines == null) {
        return false;
    }

    lines->clear();

    FILE *pipe = popen(command.c_str(), "r");
    if (pipe == null) {
        return false;
    }

    char output[256];
    while (fgets(output, sizeof(output), pipe) != null) {
        string line = output;
        size_t newline = line.find('\n');
        if (newline != string::npos) {
            line = line.substr(0, newline);
        }
        if (!line.empty() && line[line.size() - 1] == '\r') {
            line = line.substr(0, line.size() - 1);
        }

        lines->push_back(truncate_lcd_line(line));
        if ((int)lines->size() >= LOGIFRAME_MAX_LINES) {
            break;
        }
    }

    pclose(pipe);
    return !lines->empty();
}

bool G13::run_command_raw(const string &command, string *output) {
    if (command.empty() || output == null) {
        return false;
    }

    output->clear();

    FILE *pipe = popen(command.c_str(), "r");
    if (pipe == null) {
        return false;
    }

    char outputBuffer[512];
    while (fgets(outputBuffer, sizeof(outputBuffer), pipe) != null) {
        output->append(outputBuffer);
    }

    pclose(pipe);
    return !output->empty();
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

bool G13::render_logiframe_page_with_command(int index, const std::string &title) {
    string command_output;
    vector<string> lines;

    if ((index >= 0) && (index < 4) && this->run_command_raw(this->logiframe_page_cmds[index], &command_output)) {
        if (render_logiframe_raw_pbm(command_output)) {
            return true;
        }

        stringstream line_stream(command_output);
        string line;
        while (lines.size() < LOGIFRAME_MAX_LINES) {
            if (!std::getline(line_stream, line)) {
                break;
            }

            strip_cr(&line);
            lines.push_back(truncate_lcd_line(line));
        }

        if (lines.empty()) {
            lines.clear();
        }
    }

    if (lines.empty() && this->run_command_lines(this->logiframe_page_cmds[index], &lines) == false) {
        if (this->logiframe_page_cmds[index].empty()) {
            lines.push_back(title);
        }
        else {
            lines.push_back(title);
            lines.push_back("command returned no lines");
            lines.push_back("check config: " + this->logiframe_page_cmds[index]);
        }
        if (index == 1) {
            lines.push_back("no output from steam cmd");
            lines.push_back("configure lcd_logiframe_page2_cmd");
        }
        else if (index == 2) {
            lines.push_back("no output from token cmd");
            lines.push_back("configure lcd_logiframe_page3_cmd");
        }
        else if (index == 3) {
            lines.push_back("Set page4 command");
            lines.push_back("via lcd_logiframe_page4_cmd");
        }
        else {
            lines.push_back("configure page command");
            lines.push_back("in bindings file");
        }
        lines.push_back("");
    }

    while ((int)lines.size() < LOGIFRAME_MAX_LINES) {
        lines.push_back("");
    }

    return write_lines_to_lcd(lines);
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
