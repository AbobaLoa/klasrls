[app]
title = Empire 4K Calculator
package.name = empire4kcalculator
package.domain = org.dima
source.dir = .
source.include_exts = py,kv,png,jpg,atlas,json,txt,md,html,css,js
version = 0.1.0
requirements = python3,kivy
orientation = portrait
fullscreen = 0
android.permissions = SYSTEM_ALERT_WINDOW,FOREGROUND_SERVICE,INTERNET
android.api = 33
android.minapi = 26
android.archs = arm64-v8a, armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 0
