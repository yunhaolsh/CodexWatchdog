#pragma once
#include <mooncake.h>
#include <lvgl.h>
#include <string>
#include <cstdint>
#include <atomic>

// Retains the existing registration class; the launcher entry is WATCHDOG.
class AppAvatar : public mooncake::AppAbility {
public:
    AppAvatar();
    void onCreate() override;
    void onOpen() override;
    void onRunning() override;
    void onClose() override;
private:
    lv_obj_t* panel_ = nullptr;
    lv_obj_t* title_ = nullptr;
    lv_obj_t* message_ = nullptr;
    lv_obj_t* scroll_ = nullptr;
    lv_obj_t* footer_ = nullptr;
    std::string task_, state_, last_message_;
    int64_t sequence_ = -1;
    uint32_t last_seen_ = 0;
    uint32_t last_led_ = 0;
    bool online_ = false;
    bool have_status_ = false;
    bool observed_running_ = false;
    bool led_on_ = false;
    uint32_t color_ = 0;
    std::atomic<bool> playing_{false};
    void receive(const std::string& json);
    void update_led();
    void play_completion(bool success);
};
