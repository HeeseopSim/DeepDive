package com.deepdive.waitingqueue

import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** PC 서버와 통신하는 아주 작은 HTTP 클라이언트 (백그라운드 스레드에서만 호출). */
object Http {
    fun request(base: String, method: String, path: String, body: JSONObject? = null): Pair<Int, JSONObject> {
        val c = URL(base + path).openConnection() as HttpURLConnection
        try {
            c.connectTimeout = 4000
            c.readTimeout = 6000
            c.requestMethod = method
            c.useCaches = false
            if (body != null) {
                val bytes = body.toString().toByteArray(Charsets.UTF_8)
                c.doOutput = true
                c.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                c.setFixedLengthStreamingMode(bytes.size)
                c.outputStream.use { it.write(bytes) }
            }
            val code = c.responseCode
            val stream = if (code >= 400) c.errorStream else c.inputStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: "{}"
            val json = try { JSONObject(text) } catch (e: Exception) { JSONObject() }
            return code to json
        } finally {
            c.disconnect()
        }
    }
}
