plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.deepdive.waitingqueue"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.deepdive.waitingqueue"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("com.google.android.gms:play-services-code-scanner:16.1.0")  // QR 스캔 (카메라 권한 불필요)
}
