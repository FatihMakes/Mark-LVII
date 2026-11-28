package com.jarvis.companion

import android.content.Context
import android.content.Intent
import android.hardware.camera2.CameraAccessException
import android.hardware.camera2.CameraManager
import android.media.AudioManager
import android.net.Uri
import android.os.BatteryManager
import android.provider.Settings
import org.json.JSONObject

/**
 * HardwareControlBridge — Native Android Bridge for JARVIS H3.1
 * Executes hardware controls on phone: Flashlight, Volume, Brightness, Battery, Alarms & Intents.
 */
class HardwareControlBridge(private val context: Context) {

    private val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var cameraId: String? = null
    private var isTorchOn = false

    init {
        try {
            cameraId = cameraManager.cameraIdList[0]
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    fun setFlashlight(enable: Boolean): Boolean {
        return try {
            cameraId?.let {
                cameraManager.setTorchMode(it, enable)
                isTorchOn = enable
                true
            } ?: false
        } catch (e: CameraAccessException) {
            false
        }
    }

    fun setVolume(percentage: Int): Boolean {
        val maxVolume = audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        val target = ((percentage / 100.0) * maxVolume).toInt()
        audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, target, AudioManager.FLAG_SHOW_UI)
        return true
    }

    fun getBatteryLevel(): JSONObject {
        val batteryStatus: Intent? = context.registerReceiver(null, android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = batteryStatus?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = batteryStatus?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val status = batteryStatus?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val isCharging = status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL

        val pct = if (level >= 0 && scale > 0) (level * 100) / scale else 100
        return JSONObject().apply {
            put("battery_percent", pct)
            put("is_charging", isCharging)
        }
    }

    fun launchApplication(packageName: String): Boolean {
        val intent = context.packageManager.getLaunchIntentForPackage(packageName)
        return if (intent != null) {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            true
        } else {
            false
        }
    }

    fun openSystemSettings(settingType: String): Boolean {
        val action = when (settingType.lowercase()) {
            "wifi" -> Settings.ACTION_WIFI_SETTINGS
            "bluetooth" -> Settings.ACTION_BLUETOOTH_SETTINGS
            "airplane" -> Settings.ACTION_AIRPLANE_MODE_SETTINGS
            else -> Settings.ACTION_SETTINGS
        }
        val intent = Intent(action).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
        return true
    }
}
