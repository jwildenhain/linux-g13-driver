#ifndef G13_LCD_COMMAND_H
#define G13_LCD_COMMAND_H
#include <chrono>
#include <string>
#include <cerrno>
#include <fcntl.h>
#include <signal.h>
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>

extern char **environ;

// One bounded child per device; only the USB thread consumes its result.
class LcdCommand {
    pid_t pid = -1;
    int fd = -1;
    bool eof = false;
    std::chrono::steady_clock::time_point deadline;
public:
    std::string output;
    bool succeeded = false;
    LcdCommand() = default;
    LcdCommand(const LcdCommand &) = delete;
    LcdCommand &operator=(const LcdCommand &) = delete;
    ~LcdCommand() { cancel(); }
    bool running() const { return pid > 0; }
    void cancel() {
        if (pid > 0) {
            // Include descendants, e.g. the Python DDC command's ddcutil child.
            kill(-pid, SIGKILL);
            while (waitpid(pid, nullptr, 0) < 0 && errno == EINTR) {}
            pid = -1;
        }
        if (fd >= 0) { close(fd); fd = -1; }
    }
    bool start(const std::string &command, int timeout_ms = 10000) {
        cancel();
        output.clear(); succeeded = false; eof = false;
        int pipes[2];
        if (pipe2(pipes, O_CLOEXEC) < 0) return false;
        if (fcntl(pipes[0], F_SETFL, O_NONBLOCK) < 0) {
            close(pipes[0]); close(pipes[1]); return false;
        }
        posix_spawn_file_actions_t files;
        posix_spawn_file_actions_init(&files);
        posix_spawn_file_actions_adddup2(&files, pipes[1], STDOUT_FILENO);
        posix_spawn_file_actions_addclose(&files, pipes[0]);
        posix_spawn_file_actions_addclose(&files, pipes[1]);
        posix_spawnattr_t attr;
        posix_spawnattr_init(&attr);
        posix_spawnattr_setflags(&attr, POSIX_SPAWN_SETPGROUP);
        posix_spawnattr_setpgroup(&attr, 0);
        char *args[] = {const_cast<char *>("sh"), const_cast<char *>("-c"),
                        const_cast<char *>(command.c_str()), nullptr};
        int error = posix_spawn(&pid, "/bin/sh", &files, &attr, args, environ);
        posix_spawn_file_actions_destroy(&files);
        posix_spawnattr_destroy(&attr);
        close(pipes[1]);
        if (error) { close(pipes[0]); pid = -1; return false; }
        fd = pipes[0];
        deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_ms);
        return true;
    }
    // True only when a completed/failed result is available; never wait for output.
    bool poll() {
        if (!running()) return false;
        char buffer[4096];
        while (!eof) {
            ssize_t count = read(fd, buffer, sizeof(buffer));
            if (count > 0) {
                output.append(buffer, count);
                if (output.size() > 65536) { cancel(); return true; }
            } else if (count == 0) { eof = true; }
            else if (errno == EINTR) continue;
            else if (errno == EAGAIN || errno == EWOULDBLOCK) break;
            else { cancel(); return true; }
        }
        if (eof) {
            int status = 0;
            pid_t result = waitpid(pid, &status, WNOHANG);
            if (result == pid) {
                succeeded = WIFEXITED(status) && WEXITSTATUS(status) == 0;
                pid = -1;
                close(fd); fd = -1;
                return true;
            }
        }
        if (std::chrono::steady_clock::now() >= deadline) {
            cancel(); return true;
        }
        return false;
    }
};
#endif
