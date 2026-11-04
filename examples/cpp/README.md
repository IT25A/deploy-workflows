# C++ (or any other language)

The platform does not care about the language, only that your program is packaged in a container and behaves like a web server: it listens on **port 3000 on all interfaces**, and it stops when it receives `SIGTERM`.

## Files

| File | Where | Notes |
|---|---|---|
| [`main.cpp`](main.cpp) | wherever your code is | A small web server for reference (standard library and POSIX sockets only). Replace it with your program. |
| [`Dockerfile`](Dockerfile) | root | Compiles the program in a first stage and copies only the result into a small final image |
| [`app.it25a.yml`](app.it25a.yml) | root | Optional here; needed to pass settings (`GREETING`) or secrets to the program |
| [`.dockerignore`](../../templates/.dockerignore) | root | Copy it from `templates/` |

## Adapt it to your project

- **More source files:** change the compile line in the Dockerfile, for example `g++ -std=c++17 -O2 -pthread -static-libstdc++ -static-libgcc -o server src/*.cpp`.
- **CMake:** install it in the first stage and replace the compile line:

  ```dockerfile
  RUN apt-get update && apt-get install -y --no-install-recommends g++ make cmake && rm -rf /var/lib/apt/lists/*
  ...
  RUN cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j2
  ```

  Then copy `/src/build/<your-program>` in the second stage. Libraries that CMake downloads (for example with `FetchContent`) work, because the build runs on GitHub with internet access.
- **A web framework** (cpp-httplib, Crow, Drogon) makes `main.cpp` much shorter. Whatever you use, bind to `0.0.0.0` and the `PORT` variable.
- **Another language** (Rust, Go, Java, ...): keep the two-stage idea of the Dockerfile (compile in the first stage, copy the result to the second) and change the compiler image and command.

## Good to know

- The final image has no compiler, so the program must not need anything that only the build stage installs. `-static-libstdc++ -static-libgcc` puts the C++ runtime into the program; other libraries need `apt-get install` in the second stage as well.
- The Dockerfile has a **health check** that asks `/health` (answered in `main.cpp`). Keep a route with that name in your own program, or remove the `HEALTHCHECK` lines. The final image installs `curl` for it.
- Without the signal handling in `main.cpp`, stopping the container takes 10 seconds and then kills the program.
- Try it on your computer: `docker build -t cpp-demo . && docker run --rm -p 3000:3000 cpp-demo`, then open `http://localhost:3000`.
