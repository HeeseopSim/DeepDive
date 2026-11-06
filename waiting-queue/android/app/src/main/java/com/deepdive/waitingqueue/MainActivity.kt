package com.deepdive.waitingqueue

import android.app.Activity
import android.os.Bundle
import android.view.WindowManager
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import java.io.File

class MainActivity : Activity() {
    private var server: QueueServer? = null
    private var web: WebView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)  // 서버가 꺼지지 않게 화면 유지

        val view = WebView(this)
        web = view
        setContentView(view)
        view.settings.javaScriptEnabled = true
        view.settings.domStorageEnabled = true
        view.webChromeClient = WebChromeClient()  // alert/confirm 대화상자 표시
        view.webViewClient = WebViewClient()

        val assetCache = HashMap<String, String>()
        val srv = QueueServer(
            queue = WaitingQueue(File(filesDir, "data.json")),
            loadAsset = { name ->
                assetCache.getOrPut(name) { assets.open(name).bufferedReader(Charsets.UTF_8).use { it.readText() } }
            },
            joinUrl = { port -> "http://${NetUtil.lanIp() ?: "127.0.0.1"}:$port/join" },
            hint = {
                if (NetUtil.lanIp() == null) "⚠ Wi-Fi 또는 핫스팟을 켜 주세요 (현재 접속 가능한 주소가 없습니다)"
                else "같은 Wi-Fi 또는 이 폰의 핫스팟에 연결된 폰으로 QR을 찍어 주세요"
            },
        )
        server = srv
        try {
            val port = srv.start(8080)
            view.loadUrl("http://127.0.0.1:$port/")
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
