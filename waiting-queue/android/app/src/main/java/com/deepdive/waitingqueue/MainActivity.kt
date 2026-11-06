package com.deepdive.waitingqueue

import android.app.Activity
import android.content.Context
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.view.inputmethod.EditorInfo
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning

/**
 * QR 대기 등록 앱 (손님용): 대기표 화면의 QR을 스캔하거나 서버 주소를 입력하면
 * 이름/인원 등록 화면이 열리고 대기번호를 받는다.
 */
class MainActivity : Activity() {
    private lateinit var web: WebView
    private lateinit var setup: LinearLayout
    private lateinit var addr: EditText
    private lateinit var msg: TextView
    private val prefs by lazy { getSharedPreferences("cfg", Context.MODE_PRIVATE) }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#0f172a"))
        }

        // 상단 바
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(16), dp(6), dp(8), dp(6))
        }
        bar.addView(TextView(this).apply {
            text = "QR 대기 등록"
            setTextColor(Color.WHITE)
            textSize = 18f
            layoutParams = LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f)
        })
        bar.addView(Button(this).apply {
            text = "서버 변경"
            setOnClickListener { showSetup(null) }
        })
        root.addView(bar, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))

        val frame = FrameLayout(this)
        root.addView(frame, LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f))

        // 등록 화면 (WebView)
        web = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webChromeClient = WebChromeClient()  // confirm/alert 대화상자 표시
            webViewClient = object : WebViewClient() {
                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                    if (request.isForMainFrame) {
                        showSetup("서버에 연결하지 못했습니다. 주소와 Wi-Fi를 확인해 주세요. (${error.description})")
                    }
                }
            }
            visibility = View.GONE
        }
        frame.addView(web, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))

        // 서버 연결 화면
        setup = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(24), dp(24), dp(24))
            visibility = View.GONE
        }
        setup.addView(TextView(this).apply {
            text = "대기표 화면에 나온 QR을 스캔하거나,\n서버 주소를 입력해 주세요."
            setTextColor(Color.WHITE)
            textSize = 16f
        })
        setup.addView(Button(this).apply {
            text = "QR 스캔으로 연결"
            setOnClickListener { scan() }
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(20) })
        addr = EditText(this).apply {
            hint = "예: 192.168.0.10:3000"
            setHintTextColor(Color.GRAY)
            setTextColor(Color.WHITE)
            setSingleLine()
            imeOptions = EditorInfo.IME_ACTION_GO
            setOnEditorActionListener { _, _, _ -> tryConnect(text.toString()); true }
        }
        setup.addView(addr, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(16) })
        setup.addView(Button(this).apply {
            text = "연결"
            setOnClickListener { tryConnect(addr.text.toString()) }
        }, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(8) })
        msg = TextView(this).apply {
            setTextColor(Color.parseColor("#fbbf24"))
            textSize = 14f
        }
        setup.addView(msg, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT).apply { topMargin = dp(16) })
        frame.addView(setup, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))

        setContentView(root)

        val saved = prefs.getString("server", null)
        if (saved != null) connect(saved) else showSetup(null)
    }

    private fun showSetup(message: String?) {
        web.visibility = View.GONE
        setup.visibility = View.VISIBLE
        addr.setText(prefs.getString("server", "")?.removePrefix("http://") ?: "")
        msg.text = message ?: ""
    }

    private fun connect(base: String) {
        prefs.edit().putString("server", base).apply()
        setup.visibility = View.GONE
        web.visibility = View.VISIBLE
        web.loadUrl("$base/join")
    }

    /** "192.168.0.10:3000", "http://.../join" 등을 "http://host:port" 로 정리. */
    private fun normalize(raw: String): String? {
        var s = raw.trim()
        if (s.isEmpty()) return null
        if (!s.startsWith("http://") && !s.startsWith("https://")) s = "http://$s"
        val u = Uri.parse(s)
        val host = u.host ?: return null
        val port = if (u.port != -1) ":${u.port}" else ""
        return "${u.scheme}://$host$port"
    }

    private fun tryConnect(raw: String) {
        val base = normalize(raw)
        if (base == null) {
            msg.text = "주소를 확인해 주세요."
        } else {
            connect(base)
        }
    }

    private fun scan() {
        try {
            GmsBarcodeScanning.getClient(this).startScan()
                .addOnSuccessListener { b ->
                    val raw = b.rawValue
                    if (raw != null) tryConnect(raw) else msg.text = "QR에서 주소를 읽지 못했습니다."
                }
                .addOnFailureListener { e ->
                    msg.text = "QR 스캔을 사용할 수 없습니다 (${e.message}). 주소를 직접 입력해 주세요."
                }
        } catch (e: Exception) {
            msg.text = "QR 스캔을 사용할 수 없습니다. 주소를 직접 입력해 주세요."
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (web.visibility == View.VISIBLE && web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        web.destroy()
        super.onDestroy()
    }
}
