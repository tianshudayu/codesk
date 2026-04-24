package com.lensseek.codesk;

import android.content.Context;
import android.content.SharedPreferences;

public final class CloudPrefs {
    private static final String PREFS = "codesk_cloud_prefs";
    private static final String KEY_DEVICE_ACCESS_TOKEN = "device_access_token";
    private static final String KEY_SELECTED_DEVICE_ID = "selected_device_id";
    private static final String LEGACY_KEY_ACCESS_TOKEN = "access_token";

    private final SharedPreferences prefs;

    public CloudPrefs(Context context) {
        prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public String getDeviceAccessToken() {
        String token = prefs.getString(KEY_DEVICE_ACCESS_TOKEN, "");
        if (token == null || token.isBlank()) {
            token = prefs.getString(LEGACY_KEY_ACCESS_TOKEN, "");
        }
        return token == null ? "" : token;
    }

    public void setDeviceAccessToken(String value) {
        String token = value == null ? "" : value.trim();
        prefs.edit()
                .putString(KEY_DEVICE_ACCESS_TOKEN, token)
                .putString(LEGACY_KEY_ACCESS_TOKEN, token)
                .apply();
    }

    public void clearDeviceAccessToken() {
        prefs.edit()
                .remove(KEY_DEVICE_ACCESS_TOKEN)
                .remove(LEGACY_KEY_ACCESS_TOKEN)
                .apply();
    }

    public String getSelectedDeviceId() {
        return prefs.getString(KEY_SELECTED_DEVICE_ID, "");
    }

    public void setSelectedDeviceId(String value) {
        prefs.edit().putString(KEY_SELECTED_DEVICE_ID, value == null ? "" : value.trim()).apply();
    }

    public void clearSelectedDeviceId() {
        prefs.edit().remove(KEY_SELECTED_DEVICE_ID).apply();
    }

    public void clearPairing() {
        clearDeviceAccessToken();
        clearSelectedDeviceId();
    }
}
