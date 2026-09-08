#ifndef G13_STATS_AVERAGE_H
#define G13_STATS_AVERAGE_H
#include <deque>
#include <map>
#include <string>
#include <utility>
#include <cmath>

// Timestamped samples: the window is in seconds, not a fixed sample count.
class StatsAverage {
    std::map<std::string, std::deque<std::pair<double, double> > > samples;
public:
    void clear() { samples.clear(); }
    double add(const std::string &key, double value, double now, int seconds) {
        auto &queue = samples[key];
        while (!queue.empty() && queue.front().first <= now - seconds) queue.pop_front();
        if (value < 0 || !std::isfinite(value)) { queue.clear(); return -1; }
        if (!queue.empty() && queue.back().first == now) queue.pop_back();
        queue.push_back(std::make_pair(now, value));
        double sum = 0;
        for (const auto &sample : queue) sum += sample.second;
        return sum / queue.size();
    }
};
#endif
