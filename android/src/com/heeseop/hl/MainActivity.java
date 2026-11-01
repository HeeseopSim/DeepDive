package com.heeseop.hl;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.DialogInterface;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.KeyEvent;
import android.webkit.JavascriptInterface;
import android.webkit.JsResult;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import java.io.OutputStream;

public class MainActivity extends Activity {
    private WebView web;
    private ValueCallback<Uri[]> fileCallback;
    private static final int PICK = 41;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        getWindow().setStatusBarColor(Color.parseColor("#020836"));
        getWindow().setNavigationBarColor(Color.parseColor("#020836"));
        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#020836"));
        setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setUserAgentString(s.getUserAgentString() + " HLApp-Android");
        web.addJavascriptInterface(new Bridge(), "HLAndroid");
        web.setWebViewClient(new WebViewClient());
        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams p) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = cb;
                Intent i = new Intent(Intent.ACTION_GET_CONTENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("*/*");
                try {
                    startActivityForResult(Intent.createChooser(i, "Backup"), PICK);
                } catch (Exception e) {
                    fileCallback = null;
                    return false;
                }
                return true;
            }

            @Override
            public boolean onJsConfirm(WebView v, String url, String msg, final JsResult r) {
                new AlertDialog.Builder(MainActivity.this).setMessage(msg)
                    .setPositiveButton(android.R.string.ok, new DialogInterface.OnClickListener() {
                        public void onClick(DialogInterface d, int w) { r.confirm(); }
                    })
                    .setNegativeButton(android.R.string.cancel, new DialogInterface.OnClickListener() {
                        public void onClick(DialogInterface d, int w) { r.cancel(); }
                    })
                    .setOnCancelListener(new DialogInterface.OnCancelListener() {
                        public void onCancel(DialogInterface d) { r.cancel(); }
                    }).show();
                return true;
            }

            @Override
            public boolean onJsAlert(WebView v, String url, String msg, final JsResult r) {
                new AlertDialog.Builder(MainActivity.this).setMessage(msg)
                    .setPositiveButton(android.R.string.ok, new DialogInterface.OnClickListener() {
                        public void onClick(DialogInterface d, int w) { r.confirm(); }
                    })
                    .setOnCancelListener(new DialogInterface.OnCancelListener() {
                        public void onCancel(DialogInterface d) { r.confirm(); }
                    }).show();
                return true;
            }
        });
        web.loadUrl("file:///android_asset/HL.html");
    }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        if (req == PICK && fileCallback != null) {
            Uri[] out = null;
            if (res == RESULT_OK && data != null && data.getData() != null) out = new Uri[] { data.getData() };
            fileCallback.onReceiveValue(out);
            fileCallback = null;
            return;
        }
        super.onActivityResult(req, res, data);
    }

    @Override
    public boolean onKeyDown(int code, KeyEvent e) {
        if (code == KeyEvent.KEYCODE_BACK) {
            // close an open popup first; a second back press leaves the app
            web.evaluateJavascript("(function(){var o=document.querySelector('#pop:not(.hidden),#doneDlg:not(.hidden),#subModal:not(.hidden),#statModal:not(.hidden),#ddPop:not(.hidden),#cpop:not(.hidden),#viewPanel:not(.hidden),#sndPanel:not(.hidden),#printView:not(.hidden)');if(o){document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));return 1}return 0})()",
                new ValueCallback<String>() {
                    public void onReceiveValue(String v) {
                        if (!"1".equals(v)) moveTaskToBack(true);
                    }
                });
            return true;
        }
        return super.onKeyDown(code, e);
    }

    @Override
    protected void onPause() {
        web.onPause();
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
    }

    public class Bridge {
        @JavascriptInterface
        public boolean saveBackup(String name, String text) {
            try {
                ContentValues v = new ContentValues();
                v.put("_display_name", name);
                v.put("mime_type", "application/json");
                v.put("relative_path", "Download/");
                ContentResolver cr = getContentResolver();
                Uri uri = cr.insert(Uri.parse("content://media/external/downloads"), v);
                if (uri == null) return false;
                OutputStream os = cr.openOutputStream(uri);
                os.write(text.getBytes("UTF-8"));
                os.close();
                return true;
            } catch (Exception e) {
                return false;
            }
        }
    }
}
