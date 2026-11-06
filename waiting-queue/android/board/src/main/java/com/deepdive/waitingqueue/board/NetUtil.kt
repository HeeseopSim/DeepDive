package com.deepdive.waitingqueue.board

import java.net.Inet4Address
import java.net.NetworkInterface

object NetUtil {
    /** 손님 폰이 접속할 이 폰의 주소(Wi-Fi 또는 핫스팟 IPv4)를 찾는다. */
    fun lanIp(): String? {
        var best: String? = null
        var bestScore = Int.MIN_VALUE
        try {
            val ifs = NetworkInterface.getNetworkInterfaces() ?: return null
            for (ni in ifs.toList()) {
                try {
                    if (!ni.isUp || ni.isLoopback) continue
                } catch (e: Exception) { continue }
                val name = ni.name.lowercase()
                for (a in ni.inetAddresses.toList()) {
                    if (a !is Inet4Address || a.isLoopbackAddress) continue
                    val ip = a.hostAddress ?: continue
                    var score = 0
                    if (ip.startsWith("192.168.") || ip.startsWith("10.") ||
                        Regex("^172\\.(1[6-9]|2\\d|3[01])\\.").containsMatchIn(ip)) score += 10
                    if (name.startsWith("wlan") || name.startsWith("ap") || name.startsWith("swlan") ||
                        name.startsWith("rndis") || name.startsWith("eth")) score += 5
                    if (name.startsWith("rmnet") || name.startsWith("ccmni")) score -= 5  // 모바일 데이터
                    if (score > bestScore) { bestScore = score; best = ip }
                }
            }
        } catch (e: Exception) { return null }
        return best
    }
}
