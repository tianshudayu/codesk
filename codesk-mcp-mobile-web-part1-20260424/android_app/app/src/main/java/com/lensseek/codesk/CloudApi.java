package com.lensseek.codesk;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

public final class CloudApi {
    private static final int CONNECT_TIMEOUT_MS = 10000;
    private static final int READ_TIMEOUT_MS = 15000;

    public JSONObject connectPairing(String pairCode, String clientName, String platform) throws IOException, ApiException {
        JSONObject body = new JSONObject();
        try {
            body.put("pairCode", pairCode);
            body.put("clientName", clientName);
            body.put("platform", platform);
        } catch (Exception ignored) {
        }
        return requestJson("/api/pairing/connect", "POST", body.toString(), null);
    }

    public JSONObject pairingStatus(String accessToken, String deviceId) throws IOException, ApiException {
        String query = "/api/pairing/status?deviceId=" + URLEncoder.encode(deviceId == null ? "" : deviceId, StandardCharsets.UTF_8);
        return requestJson(query, "GET", null, accessToken);
    }

    public JSONObject disconnectPairing(String accessToken, String deviceId) throws IOException, ApiException {
        JSONObject body = new JSONObject();
        try {
            body.put("deviceId", deviceId);
        } catch (Exception ignored) {
        }
        return requestJson("/api/pairing/disconnect", "POST", body.toString(), accessToken);
    }

    public JSONObject bootstrap(String accessToken, String deviceId) throws IOException, ApiException {
        String query = "/api/bootstrap";
        if (deviceId != null && !deviceId.isBlank()) {
            query += "?deviceId=" + URLEncoder.encode(deviceId, StandardCharsets.UTF_8);
        }
        return requestJson(query, "GET", null, accessToken);
    }

    private JSONObject requestJson(String path, String method, String jsonBody, String accessToken) throws IOException, ApiException {
        URI uri = URI.create(BuildConfig.CLOUD_BASE_URL + path);
        HttpURLConnection connection = (HttpURLConnection) uri.toURL().openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(CONNECT_TIMEOUT_MS);
        connection.setReadTimeout(READ_TIMEOUT_MS);
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty("User-Agent", "CodeskAndroid/2.0");
        if (accessToken != null && !accessToken.isBlank()) {
            connection.setRequestProperty("Authorization", "Bearer " + accessToken.trim());
        }
        if (jsonBody != null) {
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            try (OutputStream output = connection.getOutputStream()) {
                output.write(jsonBody.getBytes(StandardCharsets.UTF_8));
            }
        }
        int status = connection.getResponseCode();
        String payload = readBody(status >= 200 && status < 300 ? connection.getInputStream() : connection.getErrorStream());
        JSONObject json;
        try {
            json = payload.isBlank() ? new JSONObject() : new JSONObject(payload);
        } catch (JSONException error) {
            throw new IOException("Invalid JSON response", error);
        }
        if (status >= 200 && status < 300) {
            return json;
        }
        String detail = json.optString("detail");
        if (detail == null || detail.isBlank()) {
            detail = "HTTP " + status;
        }
        throw new ApiException(status, detail);
    }

    private String readBody(InputStream inputStream) throws IOException {
        if (inputStream == null) {
            return "";
        }
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(inputStream, StandardCharsets.UTF_8))) {
            StringBuilder builder = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                builder.append(line);
            }
            return builder.toString();
        }
    }

    public static final class ApiException extends Exception {
        private final int statusCode;

        public ApiException(int statusCode, String message) {
            super(message);
            this.statusCode = statusCode;
        }

        public int getStatusCode() {
            return statusCode;
        }
    }
}
