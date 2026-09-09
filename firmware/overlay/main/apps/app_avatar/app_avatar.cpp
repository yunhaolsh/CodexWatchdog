#include "app_avatar.h"
#include <hal/hal.h>
#include <assets/assets.h>
#include <apps/common/common.h>
#include <ArduinoJson.hpp>
#include <esp_log.h>
#include <board.h>
#include <audio/audio_codec.h>
#include <cmath>
#include <algorithm>
#include <vector>

LV_FONT_DECLARE(font_puhui_basic_20_4);
static constexpr const char* TAG = "Watchdog";
static constexpr uint32_t BG = 0x0b1220;
static constexpr uint32_t FG = 0xe2e8f0;

static lv_obj_t* label(lv_obj_t* parent, int x, int y, int width, const lv_font_t* font) {
    auto* obj = lv_label_create(parent);
    lv_obj_set_pos(obj, x, y);
    lv_obj_set_width(obj, width);
    lv_label_set_long_mode(obj, LV_LABEL_LONG_WRAP);
    lv_obj_set_style_text_font(obj, font, 0);
    lv_obj_set_style_text_color(obj, lv_color_hex(FG), 0);
    lv_label_set_text(obj, "");
    return obj;
}

AppAvatar::AppAvatar() {
    setAppInfo().name = "WATCHDOG";
    static auto icon = assets::get_image("icon_sentinel.bin");
    setAppInfo().icon = (void*)&icon;
    static uint32_t theme = 0x38bdf8;
    setAppInfo().userData = &theme;
}
void AppAvatar::onCreate() {}

void AppAvatar::onOpen() {
    {
        LvglLockGuard lock;
        panel_ = lv_obj_create(lv_screen_active());
        lv_obj_remove_style_all(panel_);
        lv_obj_set_size(panel_, 320, 240);
        lv_obj_set_style_bg_color(panel_, lv_color_hex(BG), 0);
        lv_obj_set_style_bg_opa(panel_, LV_OPA_COVER, 0);
        lv_obj_remove_flag(panel_, LV_OBJ_FLAG_SCROLLABLE);
        auto* heading = label(panel_, 12, 7, 296, &lv_font_montserrat_14);
        lv_label_set_text(heading, "CODEX WATCHDOG");
        title_ = label(panel_, 12, 29, 296, &font_puhui_basic_20_4);
        lv_label_set_text(title_, "Connecting / 连接中");
        scroll_ = lv_obj_create(panel_);
        lv_obj_set_pos(scroll_, 10, 77);
        lv_obj_set_size(scroll_, 300, 126);
        lv_obj_set_style_bg_color(scroll_, lv_color_hex(0x162033), 0);
        lv_obj_set_style_border_width(scroll_, 0, 0);
        lv_obj_set_style_pad_all(scroll_, 7, 0);
        lv_obj_set_scroll_dir(scroll_, LV_DIR_VER);
        message_ = label(scroll_, 0, 0, 276, &font_puhui_basic_20_4);
        lv_label_set_text(message_, "Waiting for PC / 等待电脑连接");
        footer_ = label(panel_, 12, 207, 296, &lv_font_montserrat_14);
        lv_label_set_text(footer_, "Offline");
        view::create_home_indicator([this]() { close(); }, 0x38bdf8, BG);
        GetHAL().showRgbColor(0, 0, 0);
        GetHAL().onWsHeartbeat.connect([this]() { last_seen_ = GetHAL().millis(); });
        GetHAL().onWsTextMessage.connect([this](const WsTextMessage_t& msg) {
            if (!msg.watchdog_json.empty()) receive(msg.watchdog_json);
        });
    }
    GetHAL().startWebSocketAvatarService([this](std::string_view text) {
        LvglLockGuard lock;
        lv_label_set_text(message_, std::string(text).c_str());
    });
    ESP_LOGI(TAG, "Persistent task screen ready");
}

void AppAvatar::receive(const std::string& json) {
    ArduinoJson::JsonDocument doc;
    if (ArduinoJson::deserializeJson(doc, json) || doc["version"] != 1 ||
        std::string(doc["type"] | "") != "task.status" || !doc["task_id"].is<const char*>() ||
        !doc["sequence"].is<int64_t>()) return;
    std::string state = doc["state"] | "";
    if (state != "idle" && state != "running" && state != "waiting" &&
        state != "success" && state != "failed" && state != "cancelled" && state != "offline") return;
    if (std::string(doc["phase"] | "") == "cancelled") state = "cancelled";
    last_seen_ = GetHAL().millis();
    std::string task = doc["task_id"];
    int64_t sequence = doc["sequence"];
    // Equal sequence snapshots restore connectivity without replaying effects.
    if (have_status_ && task == task_ && sequence == sequence_) return;
    // A lower sequence can be a new daemon process. Accept the fresh snapshot,
    // but don't replay a completion sound across the reset.
    if (task != task_ || sequence < sequence_) {
        observed_running_ = false;
        last_message_.clear();
    }
    bool terminal = state == "success" || state == "failed" || state == "cancelled";
    bool notify = terminal && observed_running_ && state_ != state;
    task_ = task;
    sequence_ = sequence;
    state_ = state;
    have_status_ = true;
    if (state == "running" || state == "waiting") observed_running_ = true;
    if (terminal) observed_running_ = false;
    std::string message = doc["message"] | "";
    if (!message.empty()) last_message_ = message;
    if (state == "idle" && message.empty()) last_message_ = "Submit a task on PC / 请在电脑下发任务";
    color_ = state == "success" ? 0x22c55e : state == "running" || state == "failed" ? 0xef4444 :
             state == "waiting" ? 0xf59e0b : 0x94a3b8;
    {
        LvglLockGuard lock;
        std::string title = doc["title"] | state.c_str();
        lv_label_set_text(title_, title.c_str());
        lv_obj_set_style_text_color(title_, lv_color_hex(color_), 0);
        lv_label_set_text(message_, last_message_.c_str());
        lv_obj_scroll_to_y(scroll_, 0, LV_ANIM_OFF);
    }
    ESP_LOGI(TAG, "status task=%.8s state=%s seq=%lld", task_.c_str(), state_.c_str(), (long long)sequence_);
    if (notify && state != "cancelled") play_completion(state == "success");
}

void AppAvatar::update_led() {
    uint32_t now = GetHAL().millis();
    bool online = have_status_ && state_ != "offline" && last_seen_ != 0 && uint32_t(now - last_seen_) < 12000;
    bool blink = state_ == "running" || state_ == "waiting";
    bool on = online && state_ != "idle" && state_ != "cancelled";
    if (blink) on = on && ((now / (state_ == "running" ? 450 : 900)) % 2 == 0);
    if (online != online_ || on != led_on_ || uint32_t(now - last_led_) > 1000) {
        online_ = online;
        led_on_ = on;
        last_led_ = now;
        // Moderate intensity, pure red/green or amber on all 12 RGB LEDs.
        GetHAL().showRgbColor(on && state_ != "success" ? 48 : 0,
                             on && state_ == "success" ? 48 : on && state_ == "waiting" ? 24 : 0, 0);
        LvglLockGuard lock;
        std::string footer = online ? "Online  " + task_.substr(0, 8) : "OFFLINE - showing last status";
        lv_label_set_text(footer_, footer.c_str());
        lv_obj_set_style_text_color(title_, lv_color_hex(online ? color_ : 0x94a3b8), 0);
    }
}

void AppAvatar::play_completion(bool success) {
    if (playing_.exchange(true)) return;
    struct Sound { AppAvatar* app; bool success; };
    auto* sound = new Sound{this, success};
    auto result = xTaskCreate([](void* arg) {
        auto* sound = static_cast<Sound*>(arg);
        auto* codec = Board::GetInstance().GetAudioCodec();
        if (codec && !codec->output_enabled()) {
            codec->EnableOutput(true);
            int rate = codec->output_sample_rate();
            std::vector<int16_t> chunk(240);
            const float notes[] = {523.25f, 659.25f, 783.99f};
            for (int note = 0; note < 3; ++note) {
                float freq = sound->success ? notes[note] : notes[2-note] * 0.6f;
                int count = rate / 8;
                for (int start = 0; start < count; start += 240) {
                    int size = std::min(240, count - start);
                    chunk.resize(size);
                    for (int i = 0; i < size; ++i) {
                        int t = start + i;
                        float envelope = std::min(1.0f, std::min(t / 120.0f, (count-t) / 120.0f));
                        chunk[i] = int16_t(1800 * envelope * std::sin(6.2831853f * freq * t / rate));
                    }
                    codec->OutputData(chunk);
                }
            }
            codec->EnableOutput(false);
        }
        sound->app->playing_ = false;
        delete sound;
        vTaskDelete(nullptr);
    }, "watchdog_sound", 4096, sound, 3, nullptr);
    if (result != pdPASS) { delete sound; playing_ = false; }
}

void AppAvatar::onRunning() {
    update_led();
    LvglLockGuard lock;
    view::update_home_indicator();
}

void AppAvatar::onClose() {
    GetHAL().onWsTextMessage.clear();
    GetHAL().onWsHeartbeat.clear();
    while (playing_) vTaskDelay(pdMS_TO_TICKS(10));
    GetHAL().showRgbColor(0, 0, 0);
    {
        LvglLockGuard lock;
        view::destroy_home_indicator();
        lv_obj_delete(panel_);
        panel_ = nullptr;
    }
    GetHAL().requestWarmReboot(1);
}
