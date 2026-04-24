package com.lensseek.codesk;

import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.lensseek.codesk.CloudApi.ApiException;
import com.lensseek.codesk.databinding.ActivityLauncherBinding;

import org.json.JSONObject;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class LauncherActivity extends AppCompatActivity {
    private enum ScreenState {
        UNPAIRED,
        PAIRING,
        DEVICE_OFFLINE,
        DEVICE_READY
    }

    private ActivityLauncherBinding binding;
    private CloudPrefs prefs;
    private CloudApi api;
    private final ExecutorService io = Executors.newSingleThreadExecutor();

    private String deviceAccessToken = "";
    private String selectedDeviceId = "";
    private JSONObject selectedDevice = null;
    private String hintMessage = "";
    private int refreshVersion = 0;
    private boolean busy = false;
    private boolean autoOpenWhenReady = true;
    private ScreenState screenState = ScreenState.UNPAIRED;
    private String primaryAction = "open";
    private String secondaryAction = "refresh";
    private final Runnable pollRunnable = new Runnable() {
        @Override
        public void run() {
            if (isFinishing() || isDestroyed()) {
                return;
            }
            if (!busy && !deviceAccessToken.isBlank() && screenState != ScreenState.DEVICE_READY) {
                refreshState(false);
            }
            schedulePoll();
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityLauncherBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        prefs = new CloudPrefs(this);
        api = new CloudApi();
        bindStaticListeners();
        refreshState(false);
    }

    @Override
    protected void onResume() {
        super.onResume();
        refreshState(false);
        schedulePoll();
    }

    @Override
    protected void onPause() {
        super.onPause();
        binding.getRoot().removeCallbacks(pollRunnable);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        binding.getRoot().removeCallbacks(pollRunnable);
        io.shutdownNow();
    }

    private void schedulePoll() {
        if (binding == null) {
            return;
        }
        binding.getRoot().removeCallbacks(pollRunnable);
        if (!deviceAccessToken.isBlank() && screenState != ScreenState.DEVICE_READY) {
            binding.getRoot().postDelayed(pollRunnable, 2500);
        }
    }

    private void bindStaticListeners() {
        binding.pairButton.setOnClickListener(view -> connectWithPairCode());
        binding.primaryButton.setOnClickListener(view -> handlePrimaryAction());
        binding.secondaryButton.setOnClickListener(view -> handleSecondaryAction());
        binding.disconnectButton.setOnClickListener(view -> disconnectCurrentDevice());
        binding.downloadWindowsButton.setOnClickListener(view ->
                openExternal(BuildConfig.CLOUD_BASE_URL + "/api/downloads/windows-client/latest"));
    }

    private void connectWithPairCode() {
        if (busy) {
            return;
        }
        String pairCode = binding.pairCodeInput.getText().toString().replaceAll("\\D", "").trim();
        if (pairCode.length() != 6) {
            showToast(getString(R.string.pair_code_invalid));
            return;
        }
        setBusy(true, getString(R.string.pairing_in_progress));
        screenState = ScreenState.PAIRING;
        render();
        int version = ++refreshVersion;
        io.execute(() -> {
            try {
                JSONObject payload = api.connectPairing(pairCode, Build.MODEL, "android");
                String accessToken = payload.optString("accessToken");
                String deviceId = payload.optString("deviceId");
                if (accessToken == null || accessToken.isBlank() || deviceId == null || deviceId.isBlank()) {
                    throw new ApiException(502, getString(R.string.request_failed));
                }
                deviceAccessToken = accessToken;
                selectedDeviceId = deviceId;
                prefs.setDeviceAccessToken(accessToken);
                prefs.setSelectedDeviceId(deviceId);
                selectedDevice = payload.optJSONObject("device");
                hintMessage = getString(R.string.pair_success);
                autoOpenWhenReady = false;
                runOnUiThread(() -> {
                    if (!isCurrent(version)) {
                        return;
                    }
                    setBusy(false, null);
                    screenState = ScreenState.DEVICE_READY;
                    render();
                    openControlShell();
                    refreshState(false);
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isCurrent(version)) {
                        return;
                    }
                    setBusy(false, friendlyError(error));
                    screenState = ScreenState.UNPAIRED;
                    render();
                });
            }
        });
    }

    private void disconnectCurrentDevice() {
        if (deviceAccessToken.isBlank() || selectedDeviceId.isBlank() || busy) {
            clearPairingLocal();
            render();
            return;
        }
        setBusy(true, getString(R.string.disconnecting_device));
        int version = ++refreshVersion;
        io.execute(() -> {
            try {
                api.disconnectPairing(deviceAccessToken, selectedDeviceId);
                runOnUiThread(() -> {
                    if (!isCurrent(version)) {
                        return;
                    }
                    clearPairingLocal();
                    hintMessage = getString(R.string.device_disconnected);
                    setBusy(false, null);
                    render();
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isCurrent(version)) {
                        return;
                    }
                    setBusy(false, friendlyError(error));
                });
            }
        });
    }

    private void refreshState(boolean showBusy) {
        deviceAccessToken = prefs.getDeviceAccessToken();
        selectedDeviceId = prefs.getSelectedDeviceId();
        if (deviceAccessToken.isBlank() || selectedDeviceId.isBlank()) {
            selectedDevice = null;
            screenState = ScreenState.UNPAIRED;
            setBusy(false, null);
            render();
            return;
        }
        if (showBusy) {
            setBusy(true, getString(R.string.refreshing_status));
        } else {
            render();
        }
        int version = ++refreshVersion;
        io.execute(() -> {
            try {
                JSONObject payload = api.pairingStatus(deviceAccessToken, selectedDeviceId);
                JSONObject device = payload.optJSONObject("device");
                if (device == null) {
                    throw new ApiException(502, getString(R.string.device_missing));
                }
                runOnUiThread(() -> {
                    if (!isCurrent(version)) {
                        return;
                    }
                    selectedDevice = device;
                    hintMessage = "";
                    setBusy(false, null);
                    screenState = canEnterControlShell(device) ? ScreenState.DEVICE_READY : ScreenState.DEVICE_OFFLINE;
                    render();
                    if (screenState == ScreenState.DEVICE_READY && autoOpenWhenReady) {
                        autoOpenWhenReady = false;
                        openControlShell();
                    }
                });
            } catch (ApiException apiError) {
                runOnUiThread(() -> {
                    if (!isCurrent(version)) {
                        return;
                    }
                    if (apiError.getStatusCode() == 401 || apiError.getStatusCode() == 404) {
                        clearPairingLocal();
                        hintMessage = getString(R.string.device_pairing_expired);
                    } else {
                        hintMessage = friendlyError(apiError);
                    }
                    setBusy(false, null);
                    render();
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (!isCurrent(version)) {
                        return;
                    }
                    hintMessage = friendlyError(error);
                    setBusy(false, null);
                    render();
                });
            }
        });
    }

    private boolean isCurrent(int version) {
        return version == refreshVersion && !isFinishing() && !isDestroyed();
    }

    private boolean isReadyDevice(JSONObject device) {
        if (device == null) {
            return false;
        }
        String deviceState = device.optString("deviceState");
        return "ready".equalsIgnoreCase(deviceState)
                || (device.optBoolean("online")
                && device.optBoolean("cloudConnected")
                && device.optBoolean("desktopControllable")
                && device.optBoolean("backendAvailable", true));
    }

    private boolean canEnterControlShell(JSONObject device) {
        if (device == null) {
            return false;
        }
        if (isReadyDevice(device)) {
            return true;
        }
        String deviceState = device.optString("deviceState");
        return device.optBoolean("online")
                && device.optBoolean("cloudConnected")
                && device.optBoolean("backendAvailable", true)
                && !"offline".equalsIgnoreCase(deviceState)
                && !"error".equalsIgnoreCase(deviceState);
    }

    private void handlePrimaryAction() {
        if (busy) {
            return;
        }
        if ("open".equals(primaryAction)) {
            openControlShell();
            return;
        }
        refreshState(true);
    }

    private void handleSecondaryAction() {
        if (busy) {
            return;
        }
        if ("open".equals(secondaryAction)) {
            openControlShell();
            return;
        }
        refreshState(true);
    }

    private void openControlShell() {
        if (deviceAccessToken.isBlank() || selectedDeviceId.isBlank()) {
            return;
        }
        String url = BuildConfig.CLOUD_BASE_URL
                + "/app?access_token=" + Uri.encode(deviceAccessToken)
                + "&deviceId=" + Uri.encode(selectedDeviceId)
                + "&app=1&v2=1";
        Intent intent = new Intent(this, WebShellActivity.class);
        intent.putExtra(WebShellActivity.EXTRA_URL, url);
        startActivity(intent);
    }

    private void clearPairingLocal() {
        deviceAccessToken = "";
        selectedDeviceId = "";
        selectedDevice = null;
        autoOpenWhenReady = true;
        prefs.clearPairing();
        screenState = ScreenState.UNPAIRED;
    }

    private void setBusy(boolean value, String message) {
        busy = value;
        binding.progress.setVisibility(value ? View.VISIBLE : View.GONE);
        if (message != null && !message.isBlank()) {
            hintMessage = message;
        }
        binding.pairCodeInput.setEnabled(!value);
        binding.pairButton.setEnabled(!value);
        binding.primaryButton.setEnabled(!value);
        binding.secondaryButton.setEnabled(!value);
        binding.disconnectButton.setEnabled(!value);
        binding.downloadWindowsButton.setEnabled(!value);
    }

    private void render() {
        boolean paired = !deviceAccessToken.isBlank() && !selectedDeviceId.isBlank();
        if (!paired) {
            screenState = busy ? ScreenState.PAIRING : ScreenState.UNPAIRED;
        } else if (selectedDevice != null && canEnterControlShell(selectedDevice)) {
            screenState = ScreenState.DEVICE_READY;
        } else if (paired) {
            screenState = ScreenState.DEVICE_OFFLINE;
        }

        binding.bridgeStatus.setText(getString(R.string.bridge_status_line));
        binding.cloudStatus.setText(
                selectedDevice != null
                        ? describeDeviceLine(selectedDevice)
                        : getString(R.string.cloud_status_line)
        );

        binding.pairSection.setVisibility(screenState == ScreenState.UNPAIRED || screenState == ScreenState.PAIRING ? View.VISIBLE : View.GONE);
        binding.downloadWindowsButton.setVisibility(screenState == ScreenState.UNPAIRED || screenState == ScreenState.PAIRING ? View.VISIBLE : View.GONE);
        binding.disconnectButton.setVisibility(paired ? View.VISIBLE : View.GONE);
        binding.primaryButton.setVisibility(paired ? View.VISIBLE : View.GONE);
        binding.secondaryButton.setVisibility(paired ? View.VISIBLE : View.GONE);

        switch (screenState) {
            case UNPAIRED:
            case PAIRING:
                primaryAction = "open";
                secondaryAction = "refresh";
                binding.stateEyebrow.setText(getString(R.string.unpaired_eyebrow));
                binding.stateTitle.setText(getString(R.string.unpaired_title));
                binding.stateBody.setText(getString(R.string.unpaired_body));
                binding.pairStatus.setText(hintMessage == null || hintMessage.isBlank()
                        ? getString(R.string.pair_code_note)
                        : hintMessage);
                binding.pairStatus.setVisibility(View.VISIBLE);
                binding.primaryButton.setText(getString(R.string.open_codesk));
                binding.secondaryButton.setText(getString(R.string.refresh_status));
                binding.statusDetails.setText(getString(R.string.download_windows_hint));
                break;
            case DEVICE_READY:
                primaryAction = "open";
                secondaryAction = "refresh";
                binding.stateEyebrow.setText(getString(R.string.connected_eyebrow));
                binding.stateTitle.setText(getString(R.string.connected_title));
                binding.stateBody.setText(getString(R.string.connected_body));
                binding.pairStatus.setText(hintMessage == null ? "" : hintMessage);
                binding.pairStatus.setVisibility(hintMessage == null || hintMessage.isBlank() ? View.GONE : View.VISIBLE);
                binding.primaryButton.setText(getString(R.string.open_codesk));
                binding.secondaryButton.setText(getString(R.string.refresh_status));
                binding.statusDetails.setText(buildStatusDetails(selectedDevice));
                break;
            case DEVICE_OFFLINE:
            default:
                primaryAction = "refresh";
                secondaryAction = "open";
                binding.stateEyebrow.setText(getString(R.string.offline_eyebrow));
                binding.stateTitle.setText(getString(R.string.offline_title));
                binding.stateBody.setText(getString(R.string.offline_body));
                binding.pairStatus.setText(hintMessage == null ? "" : hintMessage);
                binding.pairStatus.setVisibility(hintMessage == null || hintMessage.isBlank() ? View.GONE : View.VISIBLE);
                binding.primaryButton.setText(getString(R.string.refresh_status));
                binding.secondaryButton.setText(getString(R.string.open_codesk));
                binding.statusDetails.setText(buildStatusDetails(selectedDevice));
                break;
        }
        schedulePoll();
    }

    private String describeDeviceLine(JSONObject device) {
        String alias = device.optString("alias");
        String state = device.optString("deviceState");
        String message = device.optString("deviceMessage");
        StringBuilder builder = new StringBuilder();
        if (alias != null && !alias.isBlank()) {
            builder.append(alias);
        } else {
            builder.append(getString(R.string.device_label_default));
        }
        if (state != null && !state.isBlank()) {
            builder.append(" · ").append(state);
        }
        if (message != null && !message.isBlank()) {
            builder.append(" · ").append(message);
        }
        return builder.toString();
    }

    private String buildStatusDetails(JSONObject device) {
        if (device == null) {
            return hintMessage == null ? "" : hintMessage;
        }
        String alias = device.optString("alias");
        String deviceState = device.optString("deviceState");
        String deviceMessage = device.optString("deviceMessage");
        String action = device.optString("recommendedAction");
        StringBuilder builder = new StringBuilder();
        builder.append(getString(R.string.device_row_label)).append("：").append(alias == null || alias.isBlank() ? getString(R.string.device_label_default) : alias);
        if (deviceState != null && !deviceState.isBlank()) {
            builder.append("\n").append(getString(R.string.device_state_label)).append("：").append(deviceState);
        }
        if (deviceMessage != null && !deviceMessage.isBlank()) {
            builder.append("\n").append(getString(R.string.device_message_label)).append("：").append(deviceMessage);
        }
        if (action != null && !action.isBlank()) {
            builder.append("\n").append(getString(R.string.device_action_label)).append("：").append(action);
        }
        return builder.toString();
    }

    private String friendlyError(Exception error) {
        if (error instanceof ApiException apiError) {
            int statusCode = apiError.getStatusCode();
            if (statusCode == 404) {
                return getString(R.string.pair_code_invalid);
            }
            if (statusCode == 401) {
                return getString(R.string.device_pairing_expired);
            }
            if (statusCode == 503) {
                return getString(R.string.device_temporarily_unavailable);
            }
            return apiError.getMessage();
        }
        return getString(R.string.request_failed);
    }

    private void openExternal(String url) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception ignored) {
            showToast(getString(R.string.open_link_failed));
        }
    }

    private void showToast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }
}
