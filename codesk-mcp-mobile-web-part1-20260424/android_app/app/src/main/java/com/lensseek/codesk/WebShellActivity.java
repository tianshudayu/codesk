package com.lensseek.codesk;

import android.annotation.SuppressLint;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.view.View;
import android.webkit.DownloadListener;
import android.webkit.PermissionRequest;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.appcompat.app.AppCompatActivity;

import com.lensseek.codesk.databinding.ActivityWebShellBinding;

public class WebShellActivity extends AppCompatActivity {
    public static final String EXTRA_URL = "extra_url";

    private ActivityWebShellBinding binding;
    private ValueCallback<Uri[]> pendingFileCallback;
    private final ActivityResultLauncher<String> filePickerLauncher =
            registerForActivityResult(new ActivityResultContracts.GetMultipleContents(), uris -> {
                if (pendingFileCallback == null) {
                    return;
                }
                Uri[] result = uris == null ? new Uri[0] : uris.toArray(new Uri[0]);
                pendingFileCallback.onReceiveValue(result);
                pendingFileCallback = null;
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        binding = ActivityWebShellBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        binding.retryButton.setOnClickListener(view -> loadInitialUrl());
        configureWebView();
        loadInitialUrl();
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWebView() {
        WebSettings settings = binding.webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccess(false);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setUserAgentString(settings.getUserAgentString() + " CodeskAndroid/2.0");

        binding.webView.setDownloadListener(createDownloadListener());
        binding.webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                binding.progress.setVisibility(View.GONE);
                binding.errorGroup.setVisibility(View.GONE);
                binding.webView.setVisibility(View.VISIBLE);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                String host = uri.getHost() == null ? "" : uri.getHost();
                if ("codesk.lensseekapp.com".equalsIgnoreCase(host)) {
                    return false;
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, uri));
                } catch (ActivityNotFoundException ignored) {
                    Toast.makeText(WebShellActivity.this, R.string.open_link_failed, Toast.LENGTH_SHORT).show();
                }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (!request.isForMainFrame()) {
                    return;
                }
                binding.progress.setVisibility(View.GONE);
                binding.webView.setVisibility(View.GONE);
                binding.errorGroup.setVisibility(View.VISIBLE);
            }
        });
        binding.webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> filePathCallback, FileChooserParams fileChooserParams) {
                pendingFileCallback = filePathCallback;
                filePickerLauncher.launch("image/*");
                return true;
            }

            @Override
            public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> request.grant(request.getResources()));
            }
        });
    }

    private void loadInitialUrl() {
        binding.progress.setVisibility(View.VISIBLE);
        binding.errorGroup.setVisibility(View.GONE);
        binding.webView.setVisibility(View.INVISIBLE);
        String url = getIntent().getStringExtra(EXTRA_URL);
        if (url == null || url.isBlank()) {
            url = BuildConfig.CLOUD_BASE_URL + "/app";
        }
        binding.webView.loadUrl(url);
    }

    private DownloadListener createDownloadListener() {
        return (url, userAgent, contentDisposition, mimeType, contentLength) -> {
            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, guessFileName(url, mimeType));
            request.addRequestHeader("User-Agent", userAgent);
            DownloadManager manager = getSystemService(DownloadManager.class);
            if (manager != null) {
                manager.enqueue(request);
                Toast.makeText(this, R.string.download_started, Toast.LENGTH_SHORT).show();
            }
        };
    }

    private String guessFileName(String url, String mimeType) {
        if (mimeType != null && mimeType.contains("android.package-archive")) {
            return "Codesk-Android.apk";
        }
        if (url.endsWith(".exe")) {
            return "Codesk-Setup.exe";
        }
        return Uri.parse(url).getLastPathSegment() == null ? "codesk-download" : Uri.parse(url).getLastPathSegment();
    }

    @Override
    public void onBackPressed() {
        if (binding.webView.canGoBack()) {
            binding.webView.goBack();
            return;
        }
        super.onBackPressed();
    }
}
