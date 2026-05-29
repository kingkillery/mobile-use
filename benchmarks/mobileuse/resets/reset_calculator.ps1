Write-Output "Resetting Calculator baseline state for benchmark task..."

if (Get-Command adb -ErrorAction SilentlyContinue) {
    adb shell input keyevent 3 | Out-Null
    Start-Sleep -Seconds 1
    adb shell am start -n com.google.android.calculator/.Calculator | Out-Null
    Start-Sleep -Seconds 2
    adb shell input keyevent 67 | Out-Null
    adb shell input keyevent 67 | Out-Null
    adb shell input keyevent 67 | Out-Null
    adb shell input keyevent 67 | Out-Null
    adb shell input keyevent 67 | Out-Null
}

Write-Output "Calculator reset complete."
exit 0
