package com.deepdive.waitingqueue.board

import android.graphics.Bitmap
import android.graphics.Color
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel

object Qr {
    /** 텍스트를 QR 코드 SVG 문자열로 변환 (화면에 직접 삽입). */
    fun svg(text: String, border: Int = 2): String {
        val hints = mapOf<EncodeHintType, Any>(
            EncodeHintType.MARGIN to 0,
            EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M,
            EncodeHintType.CHARACTER_SET to "UTF-8",
        )
        val m = QRCodeWriter().encode(text, BarcodeFormat.QR_CODE, 0, 0, hints)
        val n = m.width
        val s = n + border * 2
        val sb = StringBuilder()
        sb.append("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 $s $s\" shape-rendering=\"crispEdges\">")
        sb.append("<rect width=\"$s\" height=\"$s\" fill=\"#fff\"/><path fill=\"#000\" d=\"")
        for (y in 0 until n) for (x in 0 until n) if (m.get(x, y)) sb.append("M${x + border} ${y + border}h1v1h-1z")
        sb.append("\"/></svg>")
        return sb.toString()
    }

    /** 텍스트를 QR 비트맵으로 변환 (앱 화면에 직접 표시). */
    fun bitmap(text: String, size: Int = 720, border: Int = 4): Bitmap {
        val hints = mapOf<EncodeHintType, Any>(
            EncodeHintType.MARGIN to 0,
            EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M,
            EncodeHintType.CHARACTER_SET to "UTF-8",
        )
        val m = QRCodeWriter().encode(text, BarcodeFormat.QR_CODE, 0, 0, hints)
        val n = m.width
        val total = n + border * 2
        val scale = maxOf(1, size / total)
        val px = total * scale
        val pixels = IntArray(px * px) { Color.WHITE }
        for (y in 0 until n) for (x in 0 until n) {
            if (m.get(x, y)) {
                for (dy in 0 until scale) for (dx in 0 until scale) {
                    pixels[((y + border) * scale + dy) * px + (x + border) * scale + dx] = Color.BLACK
                }
            }
        }
        val bmp = Bitmap.createBitmap(px, px, Bitmap.Config.ARGB_8888)
        bmp.setPixels(pixels, 0, px, 0, 0, px, px)
        return bmp
    }
}
