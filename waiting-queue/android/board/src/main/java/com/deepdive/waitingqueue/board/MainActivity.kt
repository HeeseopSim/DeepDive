package com.deepdive.waitingqueue.board

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.view.WindowManager
import android.webkit.ConsoleMessage
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import java.io.File

/**
 * 대기표 화면 앱: 이 기기가 서버가 되어 대기열을 관리하고, 대기표 화면(번호/다음 순서/QR)을 띄운다.
 * 상단에 "서버 주소"를 항상 표시한다 (QR 등록 앱의 서버 주소 입력칸에 그대로 입력).
 */
class MainActivity : Activity() {
    private var server: QueueServer? = null
    private lateinit var web: WebView
    private lateinit var status: TextView
    private lateinit var debug: TextView
    private val handler = Handler(Looper.getMainLooper())
    private var port = 0
    private var base = ""

    private val ticker = object : Runnable {
        override fun run() {
            updateStatus()
            handler.postDelayed(this, 3000)
        }
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    private fun updateStatus() {
        val ip = NetUtil.lanIp()
        status.text = when {
            port == 0 -> "❌ 서버를 시작하지 못했습니다"
            ip == null -> "⚠ Wi-Fi/핫스팟이 꺼져 있습니다 (이 기기에서만 127.0.0.1:$port)"
            else -> "✅ 서버 주소: $ip:$port   (등록 앱에 이 주소를 입력하세요)"
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        val dark = Color.parseColor("#0b1220")
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(dark)
        }
        status = TextView(this).apply {
            setTextColor(Color.WHITE)
            textSize = 16f
            setTextIsSelectable(true)
            setPadding(dp(12), dp(8), dp(12), dp(8))
            text = "서버 시작 중…"
        }
        debug = TextView(this).apply {
            setTextColor(Color.parseColor("#fca5a5"))
            textSize = 12f
            setPadding(dp(12), dp(4), dp(12), dp(4))
            setTextIsSelectable(true)
        }
        web = WebView(this).apply {
            setBackgroundColor(dark)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webChromeClient = object : WebChromeClient() {
                override fun onConsoleMessage(cm: ConsoleMessage): Boolean {
                    if (cm.messageLevel() == ConsoleMessage.MessageLevel.ERROR) {
                        debug.text = "JS 오류: ${cm.message()} (줄 ${cm.lineNumber()})"
                    }
                    return true
                }
            }
            webViewClient = object : WebViewClient() {
                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                    if (request.isForMainFrame) debug.text = "페이지 오류: ${error.description} (${request.url})"
                }
                override fun onPageFinished(view: WebView, url: String) {
                    debug.text = if (debug.text.isNullOrEmpty()) "" else debug.text
                }
            }
        }
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        bar.addView(Button(this).apply {
            text = "대기표 화면"
            setOnClickListener { debug.text = ""; web.loadUrl("$base/board") }
        }, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
        bar.addView(Button(this).apply {
            text = "관리 (수동 추가/삭제)"
            setOnClickListener { debug.text = ""; web.loadUrl("$base/") }
        }, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))

        root.addView(status, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        root.addView(bar, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        root.addView(web, LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f))
        root.addView(debug, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        setContentView(root)

        val cache = HashMap<String, String>()
        val srv = QueueServer(
            queue = WaitingQueue(File(filesDir, "data.json")),
            loadAsset = { name ->
                cache.getOrPut(name) { assets.open(name).bufferedReader(Charsets.UTF_8).use { it.readText() } }
            },
            joinUrl = { p -> "http://${NetUtil.lanIp() ?: "127.0.0.1"}:$p/join" },
            hint = {
                if (NetUtil.lanIp() == null) "⚠ Wi-Fi 또는 핫스팟을 켜 주세요 (현재 접속 가능한 주소가 없습니다)"
                else "같은 Wi-Fi 또는 이 기기의 핫스팟에 연결된 폰으로 QR을 찍어 주세요"
            },
        )
        server = srv
        try {
            port = srv.start(8080)
            base = "http://127.0.0.1:$port"
            web.loadUrl("$base/board")
        } catch (e: Exception) {
            debug.text = "서버 시작 오류: ${e.message}"
        }
        handler.post(ticker)
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        handler.removeCallbacks(ticker)
        server?.stop()
        web.destroy()
        super.onDestroy()
    }
}
