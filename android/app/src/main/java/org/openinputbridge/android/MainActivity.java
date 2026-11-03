package org.openinputbridge.android;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

/**
 * v0.6: small, foreground-only shell for the known-working browser bridge.
 * No AccessibilityService, BLE HID capture, background service or JS interface.
 */
public final class MainActivity extends Activity {
    private static final int BG = 0xFF101B2C, PANEL = 0xFF182B42;
    private static final int TEXT = 0xFFF2F6FC, MUTED = 0xFFBACADA, ACCENT = 0xFF79E3BF;
    private static final String PREFS = "bridge_settings", KEY_LINK = "link";
    private WebView webView;
    private String address;
    private String siteOrigin;
    private boolean bridgeMode = false;
    private boolean resumed = false;
    private boolean pageLoaded = false;
    private EditText addressInput;

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        address = getSharedPreferences(PREFS, MODE_PRIVATE).getString(KEY_LINK, "");
        if (savedInstanceState != null) {
            bridgeMode = savedInstanceState.getBoolean("bridgeMode", !address.isEmpty());
        } else {
            bridgeMode = !address.isEmpty();
        }
        if (bridgeMode && isValidAddress(address)) showBridge();
        else showSettings(null);
    }

    private static String validate(String input) {
        try {
            Uri uri = Uri.parse(input.trim());
            if (!"http".equals(uri.getScheme()) || uri.getUserInfo() != null
                    || uri.getFragment() != null || uri.getPort() <= 0 || uri.getPort() > 65535
                    || !"/".equals(uri.getPath())) return null;
            String host = uri.getHost();
            if (host == null || !host.matches("[0-9]{1,3}(\\.[0-9]{1,3}){3}")) return null;
            String[] parts = host.split("\\.");
            int[] octets = new int[4];
            for (int i = 0; i < 4; i++) {
                octets[i] = Integer.parseInt(parts[i]);
                if (octets[i] > 255) return null;
            }
            int a = octets[0], b = octets[1];
            if (!(a == 10 || a == 192 && b == 168 || a == 172 && b >= 16 && b <= 31))
                return null;
            String token = uri.getQueryParameter("token");
            if (token == null || !token.matches("[A-Za-z0-9_-]{12,128}")) return null;
            if (uri.getQueryParameterNames().size() != 1) return null;
            return "http://" + host + ":" + uri.getPort() + "/?token=" + token;
        } catch (RuntimeException ex) {
            return null;
        }
    }

    private static boolean isValidAddress(String input) {
        return validate(input) != null;
    }

    private String expectedOrigin() {
        Uri uri = Uri.parse(address);
        return "http://" + uri.getHost() + ":" + uri.getPort();
    }

    private void showSettings(String error) {
        stopPage();
        bridgeMode = false;
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        LinearLayout root = vertical();
        root.setPadding(dp(22), dp(32), dp(22), dp(20));
        root.setBackgroundColor(BG);
        TextView heading = label("Open Input Bridge", 26, TEXT, true);
        add(root, heading, 12);
        add(root, label("前台专用 · 不需要无障碍权限", 14, ACCENT, true), 22);
        add(root, label("先在 Windows 运行 WebSocket 服务，将电脑终端显示的完整手机访问地址粘贴到这里。", 14, MUTED, false), 16);
        if (error != null) add(root, label(error, 14, 0xFFFFC58A, false), 14);
        addressInput = new EditText(this);
        addressInput.setText(address);
        addressInput.setSelectAllOnFocus(true);
        addressInput.setSingleLine(true);
        addressInput.setTextSize(14);
        addressInput.setTextColor(TEXT);
        addressInput.setHintTextColor(0xFF889AB0);
        addressInput.setHint("http://192.168.x.x:8766/?token=...");
        addressInput.setBackground(shape(PANEL));
        addressInput.setPadding(dp(12), dp(12), dp(12), dp(12));
        add(root, addressInput, 18);
        Button connect = button("连接并进入桥接");
        connect.setOnClickListener(v -> {
            String input = validate(addressInput.getText().toString());
            if (input == null) {
                Toast.makeText(this, "请填写完整的私人局域网地址（包括 token）", Toast.LENGTH_LONG).show();
                return;
            }
            address = input;
            getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(KEY_LINK, address).apply();
            ((InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE))
                    .hideSoftInputFromWindow(addressInput.getWindowToken(), 0);
            showBridge();
        });
        add(root, connect, 16);
        add(root, label("退出或切换到其他手机应用时，Windows 控制立即停用。返回 Open Input Bridge 后自动恢复。", 13, MUTED, false), 8);
        add(root, label("仅限可信任的私人 Wi-Fi；不要将 Windows 端口暴露到互联网。", 12, MUTED, false), 0);
        setContentView(root);
    }

    private void showBridge() {
        String checked = validate(address);
        if (checked == null) {
            showSettings("连接地址已失效，请重新输入。");
            return;
        }
        address = checked;
        siteOrigin = expectedOrigin();
        bridgeMode = true;
        pageLoaded = false;
        LinearLayout root = vertical();
        root.setBackgroundColor(BG);

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.setPadding(dp(14), dp(6), dp(14), dp(6));
        top.setBackgroundColor(PANEL);
        TextView heading = label("Open Input Bridge · 前台桥接", 15, TEXT, true);
        top.addView(heading, new LinearLayout.LayoutParams(0, dp(44), 1));
        Button settings = button("设置");
        settings.setTextSize(13);
        settings.setOnClickListener(v -> showSettings(null));
        top.addView(settings, new LinearLayout.LayoutParams(dp(82), dp(44)));
        root.addView(top);

        webView = new WebView(this);
        webView.setBackgroundColor(BG);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(false);
        webView.getSettings().setAllowContentAccess(false);
        webView.getSettings().setAllowFileAccessFromFileURLs(false);
        webView.getSettings().setAllowUniversalAccessFromFileURLs(false);
        webView.getSettings().setMixedContentMode(android.webkit.WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        webView.getSettings().setMediaPlaybackRequiresUserGesture(true);
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        webView.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                // Do not navigate away from the configured local server or load untrusted URLs.
                return !("http".equals(uri.getScheme())
                        && siteOrigin.equals("http://" + uri.getHost() + ":" + uri.getPort())
                        && "/".equals(uri.getPath()));
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (webView != view) return;
                if ("about:blank".equals(url)) return;
                pageLoaded = true;
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (webView == view && request.isForMainFrame() && bridgeMode) {
                    showSettings("无法连接电脑，请检查 Windows 终端和 Wi-Fi。");
                }
            }
            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request,
                                                        android.webkit.WebResourceResponse response) {
                if (webView == view && request.isForMainFrame() && response.getStatusCode() == 403)
                    showSettings("地址中的 token 已过期，请从电脑终端复制新的完整地址。");
            }
        });
        root.addView(webView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(root);
        startPageIfVisible();
    }

    private void startPageIfVisible() {
        if (!bridgeMode || webView == null || !resumed || !hasWindowFocus()) return;
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if (!pageLoaded) {
            // Never send actions unless the app is foreground. This document will
            // be discarded on loss of focus, cancelling pending double-tap timers.
            webView.loadUrl(address);
            pageLoaded = true;
        }
        webView.onResume();
    }

    private void stopPage() {
        if (webView != null) {
            // Destroying the document also closes its WebSocket; no queued or
            // delayed tap may be sent after the user leaves the foreground.
            WebView old = webView;
            webView = null;
            old.stopLoading();
            old.loadUrl("about:blank");
            old.onPause();
            old.destroy();
        }
        pageLoaded = false;
    }

    private void suspendPage() {
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        if (webView != null) {
            webView.loadUrl("about:blank");
            webView.onPause();
            pageLoaded = false;
        }
    }

    @Override protected void onResume() {
        super.onResume();
        resumed = true;
        startPageIfVisible();
    }
    @Override protected void onPause() {
        resumed = false;
        suspendPage();
        super.onPause();
    }
    @Override public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (!hasFocus) suspendPage();
        else startPageIfVisible();
    }
    @Override public void onBackPressed() {
        if (bridgeMode) showSettings(null);
        else super.onBackPressed();
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        state.putBoolean("bridgeMode", bridgeMode);
        super.onSaveInstanceState(state);
    }
    @Override protected void onDestroy() {
        stopPage();
        super.onDestroy();
    }
    private LinearLayout vertical() {
        LinearLayout l = new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        return l;
    }
    private TextView label(String text, int size, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setGravity(Gravity.CENTER_VERTICAL);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }
    private Button button(String title) {
        Button b = new Button(this);
        b.setText(title);
        b.setTextColor(TEXT);
        b.setAllCaps(false);
        b.setBackground(shape(0xFF31557C));
        return b;
    }
    private GradientDrawable shape(int color) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(12));
        return d;
    }
    private void add(LinearLayout parent, View child, int bottom) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1, -2);
        lp.bottomMargin = dp(bottom);
        parent.addView(child, lp);
    }
    private int dp(float value) { return Math.round(getResources().getDisplayMetrics().density * value); }
}
