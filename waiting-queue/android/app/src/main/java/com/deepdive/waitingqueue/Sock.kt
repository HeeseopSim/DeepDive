package com.deepdive.waitingqueue

import org.json.JSONObject
import java.io.BufferedReader
import java.io.IOException
import java.io.InputStreamReader
import java.net.InetSocketAddress
import java.net.Socket

/**
 * PC 서버와 TCP 소켓으로 통신 (줄 단위 JSON).
 * 요청 1개 = 연결 → 한 줄 전송 → 한 줄 수신 → 닫기. 백그라운드 스레드에서만 호출할 것.
 */
object Sock {
    fun call(host: String, port: Int, req: JSONObject): JSONObject {
        val s = Socket()
        try {
            s.connect(InetSocketAddress(host, port), 4000)
            s.soTimeout = 6000
            val out = s.getOutputStream()
            out.write((req.toString() + "\n").toByteArray(Charsets.UTF_8))
            out.flush()
            val line = BufferedReader(InputStreamReader(s.getInputStream(), Charsets.UTF_8)).readLine()
                ?: throw IOException("서버가 응답 없이 연결을 닫았습니다")
            return JSONObject(line)
        } finally {
            try { s.close() } catch (e: Exception) { }
        }
    }
}
