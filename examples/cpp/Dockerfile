# C++ program. Save as "Dockerfile" in the root of your repository.
#
# Before you use it, check:
#   - the program listens on the port from the PORT variable (default 3000) on 0.0.0.0
#   - the compile command below builds your program (add your .cpp files, or switch to CMake, see README.md)

# Stage 1 "build": a Linux with the compiler. This stage is thrown away after the build.
FROM debian:trixie-slim AS build
RUN apt-get update && apt-get install -y --no-install-recommends g++ make && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY . .
# -static-libstdc++ and -static-libgcc put the C++ runtime into the program, so it also runs in a slim image.
RUN g++ -std=c++17 -O2 -pthread -static-libstdc++ -static-libgcc -o server main.cpp

# Stage 2: the final image only contains the compiled program, no compiler.
FROM debian:trixie-slim
# curl is only needed for the health check below.
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /src/server ./server
ENV PORT=3000
EXPOSE 3000
USER nobody

# Health check: Docker asks the program every 10 seconds whether it is alive. The deployment waits until
# the first check succeeds; if it never does, the update is rolled back and the old version keeps running.
# main.cpp answers "/health" with status 200.
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:3000/health || exit 1

CMD ["./server"]
