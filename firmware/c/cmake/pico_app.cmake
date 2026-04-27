# add_pico_app(<name>)
#
# Registers an executable for src/apps/<name>/<name>.c. If a matching
# <name>.pio sits next to it, generates the PIO header automatically.
# Links the common Pico libraries used across this project's apps;
# extend LINK_LIBS or add per-app target_link_libraries() calls as needed.
function(add_pico_app name)
    set(app_dir ${CMAKE_SOURCE_DIR}/src/apps/${name})
    set(app_src ${app_dir}/${name}.c)
    set(app_pio ${app_dir}/${name}.pio)

    add_executable(${name} ${app_src})
    target_include_directories(${name} PRIVATE ${CMAKE_SOURCE_DIR}/src)

    if(EXISTS ${app_pio})
        pico_generate_pio_header(${name} ${app_pio})
    endif()

    target_link_libraries(${name}
        pico_stdlib
        hardware_pio
        hardware_clocks
        pico_cyw43_arch_none
    )

    pico_enable_stdio_usb(${name} 1)
    pico_enable_stdio_uart(${name} 0)

    pico_add_extra_outputs(${name})
endfunction()
