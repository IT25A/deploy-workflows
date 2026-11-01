// A minimal web server in C++17 that only needs the standard library and POSIX sockets.
// It shows what the platform expects from ANY program, whatever language it is written in:
//   - listen on the port from the PORT variable (default 3000) on ALL interfaces (0.0.0.0)
//   - stop cleanly when the container is stopped (SIGTERM)
//   - read configuration from environment variables
// For a real project you would use a library (for example cpp-httplib, Crow or Drogon) instead of raw sockets.
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#include <atomic>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>
#include <thread>

static std::atomic<bool> running{true};

// Docker stops a container with SIGTERM. A program that runs as the main process of a container
// ignores it by default and is killed after 10 seconds, so we handle it.
static void on_signal(int) { running = false; }

static std::string env(const char* name, const std::string& fallback) {
    const char* value = std::getenv(name);
    return (value && *value) ? value : fallback;
}

static std::string respond(int status, const char* reason, const char* type, const std::string& body) {
    return "HTTP/1.1 " + std::to_string(status) + " " + reason + "\r\n" +
           "Content-Type: " + type + "\r\n" +
           "Content-Length: " + std::to_string(body.size()) + "\r\n" +
           "Connection: close\r\n\r\n" + body;
}

static void handle(int client) {
    timeval timeout{5, 0};  // do not wait forever for slow clients
    setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);

    char buffer[4096];
    ssize_t received = recv(client, buffer, sizeof buffer - 1, 0);
    if (received <= 0) { close(client); return; }
    buffer[received] = '\0';

    // First line of the request: "GET /path HTTP/1.1"
    std::string line(buffer, std::strcspn(buffer, "\r\n"));
    std::string method = line.substr(0, line.find(' '));
    std::string path = line.size() > method.size() + 1
        ? line.substr(method.size() + 1, line.find(' ', method.size() + 1) - method.size() - 1) : "/";

    std::string reply;
    if (method != "GET") {
        reply = respond(405, "Method Not Allowed", "text/plain", "Only GET is supported.\n");
    } else if (path == "/health") {
        reply = respond(200, "OK", "text/plain", "ok\n");
    } else if (path == "/") {
        std::string greeting = env("GREETING", "Hello from C++");  // a plain setting from it25a.yml
        reply = respond(200, "OK", "text/html; charset=utf-8", "<h1>" + greeting + "</h1>\n");
    } else {
        reply = respond(404, "Not Found", "text/plain", "Not found.\n");
    }
    send(client, reply.data(), reply.size(), MSG_NOSIGNAL);
    close(client);
}

int main() {
    int port = std::atoi(env("PORT", "3000").c_str());

    struct sigaction action {};
    action.sa_handler = on_signal;  // no SA_RESTART: accept() must return when the signal arrives
    sigaction(SIGTERM, &action, nullptr);
    sigaction(SIGINT, &action, nullptr);

    int server = socket(AF_INET, SOCK_STREAM, 0);
    int yes = 1;
    setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof yes);

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_ANY);  // 0.0.0.0: reachable from outside the container
    address.sin_port = htons(static_cast<uint16_t>(port));
    if (bind(server, reinterpret_cast<sockaddr*>(&address), sizeof address) != 0 || listen(server, 64) != 0) {
        std::perror("bind/listen");
        return 1;
    }
    std::printf("listening on port %d\n", port);
    std::fflush(stdout);

    while (running) {
        int client = accept(server, nullptr, nullptr);
        if (client < 0) continue;                 // interrupted by a signal or a failed connection
        std::thread(handle, client).detach();     // one thread per request, fine for a course project
    }
    close(server);
    std::printf("stopped\n");
    return 0;
}
