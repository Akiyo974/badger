plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.christendijoux.badgerremote"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.christendijoux.badgerremote"
        // Wear OS 3+: Galaxy Watch 4 and newer
        minSdk = 30
        targetSdk = 35
        versionCode = 2
        versionName = "0.2.0"
    }

    // Fixed signing key, provided by CI (GitHub secrets) or locally through environment variables.
    // Without them, the release APK is built unsigned.
    val signingStore = System.getenv("SIGNING_STORE_FILE")?.let { file(it) }
    signingConfigs {
        if (signingStore != null) {
            create("release") {
                storeFile = signingStore
                storePassword = System.getenv("SIGNING_STORE_PASSWORD")
                keyAlias = System.getenv("SIGNING_KEY_ALIAS")
                keyPassword = System.getenv("SIGNING_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            if (signingStore != null) signingConfig = signingConfigs.getByName("release")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.tooling.preview)

    implementation(libs.wear.compose.material)
    implementation(libs.wear.compose.foundation)

    implementation(libs.health.services.client)
    implementation(libs.androidx.concurrent.futures.ktx)
    implementation(libs.guava)

    testImplementation(libs.junit)

    debugImplementation(libs.androidx.compose.ui.tooling)
    debugImplementation(libs.wear.compose.ui.tooling)
}
