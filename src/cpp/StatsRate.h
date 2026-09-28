#ifndef G13_STATS_RATE_H
#define G13_STATS_RATE_H
#include <cmath>

// Counters may reset after a device reconnect. Elapsed time must come from
// steady_clock, with fractional seconds retained until the final display.
inline double bytes_per_second(unsigned long long current,
                               unsigned long long previous, double elapsed) {
    if (current < previous || elapsed <= 0 || !std::isfinite(elapsed)) return 0;
    return static_cast<double>(current - previous) / elapsed;
}
#endif
