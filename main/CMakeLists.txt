idf_component_register(
    SRCS
        "main.c"
        "link_dbus.c"
        "wifi.c"
        "tcp_bridge.c"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        esp_wifi
        esp_netif
        esp_event
        esp_timer
        nvs_flash
        lwip
)
