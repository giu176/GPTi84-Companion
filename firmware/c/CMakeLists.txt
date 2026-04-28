cmake_minimum_required(VERSION 3.13)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

set(PICO_BOARD pico_w CACHE STRING "Board type")

get_filename_component(_repo_root ${CMAKE_CURRENT_LIST_DIR}/../.. ABSOLUTE)
if(EXISTS ${_repo_root}/vendor/pico-sdk/pico_sdk_init.cmake)
    set(PICO_SDK_PATH ${_repo_root}/vendor/pico-sdk)
elseif(DEFINED ENV{PICO_SDK_PATH})
    set(PICO_SDK_PATH $ENV{PICO_SDK_PATH})
elseif(EXISTS /usr/share/pico-sdk/pico_sdk_init.cmake)
    set(PICO_SDK_PATH /usr/share/pico-sdk)
else()
    message(FATAL_ERROR
        "pico-sdk not found. Run: git submodule update --init --recursive vendor/pico-sdk")
endif()

include(${PICO_SDK_PATH}/pico_sdk_init.cmake)

project(ti84_superdeluxe C CXX ASM)

pico_sdk_init()

# CPM.cmake -- vendored, version-pinned. Set CPM_SOURCE_CACHE in the env
# (e.g. ~/.cache/CPM) to share fetched deps across projects.
include(${CMAKE_CURRENT_LIST_DIR}/cmake/CPM.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/cmake/pico_app.cmake)

add_pico_app(bringup)
add_pico_app(dbus_bringup)
