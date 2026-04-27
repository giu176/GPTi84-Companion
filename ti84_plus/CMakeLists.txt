cmake_minimum_required(VERSION 3.13)

project(ti84_plus_tools C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug)
endif()

add_compile_options(-Wall -Wextra -Wpedantic)

add_executable(decoder ti84_plus_255/src/decoder.c)
add_executable(encoder ti84_plus_255/src/encoder.c)

# Headless TilEm harness + companion HELLO.8Xp generator.
# Both link against libtifiles2/libticalcs2/libticables2 from the system
# and (for the harness) the vendored libtilemcore.a.

find_package(PkgConfig REQUIRED)
pkg_check_modules(TILIBS REQUIRED tifiles2 ticalcs2 ticables2)

set(TILEM_DIR "${CMAKE_SOURCE_DIR}/../vendor/tilem")
set(TILEM_LIB "${TILEM_DIR}/build/emu/libtilemcore.a")

if(NOT EXISTS "${TILEM_LIB}")
    message(WARNING
        "libtilemcore.a not found at ${TILEM_LIB}. "
        "Run \`just emu-build\` first; the headless target will fail to link until then.")
endif()

add_executable(mk_hello_8xp headless/mk_hello_8xp.c)
target_include_directories(mk_hello_8xp PRIVATE ${TILIBS_INCLUDE_DIRS})
target_compile_options(mk_hello_8xp PRIVATE ${TILIBS_CFLAGS_OTHER})
target_link_libraries(mk_hello_8xp PRIVATE ${TILIBS_LIBRARIES})

add_executable(tilem_headless headless/headless.c headless/tilem_embed.c)
target_include_directories(tilem_headless PRIVATE
    ${TILIBS_INCLUDE_DIRS}
    "${TILEM_DIR}/emu")
target_compile_options(tilem_headless PRIVATE ${TILIBS_CFLAGS_OTHER})
target_link_libraries(tilem_headless PRIVATE
    "${TILEM_LIB}"
    ${TILIBS_LIBRARIES}
    m)

add_executable(link_loopback headless/link_loopback.c headless/tilem_embed.c)
target_include_directories(link_loopback PRIVATE
    ${TILIBS_INCLUDE_DIRS}
    "${TILEM_DIR}/emu")
target_compile_options(link_loopback PRIVATE ${TILIBS_CFLAGS_OTHER})
target_link_libraries(link_loopback PRIVATE
    "${TILEM_LIB}"
    ${TILIBS_LIBRARIES}
    m)
