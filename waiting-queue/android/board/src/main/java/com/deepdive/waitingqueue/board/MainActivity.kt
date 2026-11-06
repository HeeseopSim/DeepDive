package com.deepdive.waitingqueue.board

import android.app.Activity
import android.graphics.Color
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.ViewGroup.LayoutParams.WRAP_CONTENT
import android.view.WindowManager
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.Toast
import java.io.File

/**
 * 대기표 화면 앱: 이 기기가 서버가 되어 대기열을 관리하고, 대기표 화면(번호/다음 순서/QR)을 띄운다.
 * 손님은 "QR 대기 등록" 앱(또는 폰 카메라)으로 QR을 찍어 등록한다.
 */
class MainActivity : Activity() {
    private var server: QueueServer? = null
    private var web: WebView? = null
    private var base = ""

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)  // 서버가 꺼지지 않게 화면 유지

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#0b1220"))
        }
        val bar = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val view = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            webChromeClient = WebChromeClient()
            webViewClient = WebViewClient()
        }
        web = view
        val b1 = Button(this).apply { text = "대기표 화면"; setOnClickListener { view.loadUrl("$base/board") } }
        val b2 = Button(this).apply { text = "관리 (수동 추가/삭제)"; setOnClickListener { view.loadUrl("$base/") } }
        bar.addView(b1, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
        bar.addView(b2, LinearLayout.LayoutParams(0, WRAP_CONTENT, 1f))
        root.addView(bar, LinearLayout.LayoutParams(MATCH_PARENT, WRAP_CONTENT))
        root.addView(view, LinearLayout.LayoutParams(MATCH_PARENT, 0, 1f))
        setContentView(root)

        val cache = HashMap<String, String>()
        val srv = QueueServer(
            queue = WaitingQueue(File(filesDir, "data.json")),
            loadAsset = { name ->
                cache.getOrPut(name) { assets.open(name).bufferedReader(Charsets.UTF_8).use { it.readText() } }
            },
            joinUrl = { port -> "http://${NetUtil.lanIp() ?: "127.0.0.1"}:$port/join" },
            hint = {
                if (NetUtil.lanIp() == null) "⚠ Wi-Fi 또는 핫스팟을 켜 주세요 (현재 접속 가능한 주소가 없습니다)"
                else "같은 Wi-Fi 또는 이 기기의 핫스팟에 연결된 폰으로 QR을 찍어 주세요"
            },
        )
        server = srv
        try {
            val port = srv.start(8080)
            base = "http://127.0.0.1:$port"
            view.loadUrl("$base/board")
        } catch (e: Exception) {
            Toast.makeText(this, "서버를 시작하지 못했습니다: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        val w = web
        if (w != null && w.canGoBack()) w.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        server?.stop()
        web?.destroy()
        super.onDestroy()
    }
}
