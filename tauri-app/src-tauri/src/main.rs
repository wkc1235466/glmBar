// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use glmbar_lib::commands::AppState;
use glmbar_lib::config::store;
use glmbar_lib::tray;
use std::time::Duration;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    Emitter, Manager, RunEvent,
};

fn main() {
    let config = store::load_config();

    let http_client = reqwest::Client::builder()
        .timeout(Duration::from_secs(15))
        .build()
        .expect("Failed to create HTTP client");

    tauri::Builder::default()
        .manage(AppState {
            config: tokio::sync::Mutex::new(config),
            http_client,
        })
        .invoke_handler(tauri::generate_handler![
            glmbar_lib::commands::get_config,
            glmbar_lib::commands::save_config,
            glmbar_lib::commands::fetch_all_usage,
            glmbar_lib::commands::parse_curl_command,
            glmbar_lib::commands::get_available_provider_types,
            glmbar_lib::commands::get_provider_fields,
            glmbar_lib::commands::show_settings_window,
        ])
        .setup(|app| {
            // Build tray menu
            let refresh_item = MenuItem::with_id(app, "refresh", "刷新", true, None::<&str>)?;
            let settings_item = MenuItem::with_id(app, "settings", "设置", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "退出", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&refresh_item, &settings_item, &quit_item])?;

            // Create initial tray icon
            let icon_bytes = tray::create_usage_icon(None);
            let icon = tauri::image::Image::from_bytes(&icon_bytes)
                .expect("Failed to create tray icon");

            let _tray = TrayIconBuilder::new()
                .icon(icon)
                .tooltip("GlmBar - 编程套餐用量")
                .menu(&menu)
                .on_menu_event(move |app, event| {
                    match event.id.as_ref() {
                        "refresh" => {
                            let _ = app.emit("trigger-refresh", ());
                        }
                        "settings" => {
                            if let Some(window) = app.get_webview_window("settings") {
                                let _ = window.show();
                                let _ = window.set_focus();
                            }
                        }
                        "quit" => {
                            std::process::exit(0);
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    if let tauri::tray::TrayIconEvent::Click {
                        button: tauri::tray::MouseButton::Left,
                        button_state: tauri::tray::MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        toggle_popup_window(app);
                    }
                })
                .build(app)?;

            // Start background refresh timer using Tauri's built-in async runtime
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let mut interval = tokio::time::interval(Duration::from_secs(60));
                let mut last_avg: Option<f64> = None;

                loop {
                    interval.tick().await;

                    // Fetch usage and emit
                    let state = app_handle.state::<AppState>();
                    let (enabled, refresh_secs, client) = {
                        let config = state.config.lock().await;
                        let pcs: Vec<_> =
                            config.providers.iter().filter(|p| p.enabled).cloned().collect();
                        (pcs, config.refresh_interval_seconds, state.http_client.clone())
                    };

                    // Update interval
                    interval = tokio::time::interval(Duration::from_secs(refresh_secs));

                    let mut handles = Vec::new();
                    for pc in enabled {
                        let provider = glmbar_lib::providers::create_provider(&pc, &client);
                        handles
                            .push(tokio::spawn(async move { provider.fetch_usage().await }));
                    }

                    let mut results = Vec::new();
                    for handle in handles {
                        match handle.await {
                            Ok(data) => results.push(data),
                            Err(e) => results.push(
                                glmbar_lib::providers::models::UsageData::error(
                                    "unknown",
                                    "Unknown",
                                    &e.to_string(),
                                ),
                            ),
                        }
                    }

                    // Calculate average percentage
                    let percents: Vec<f64> = results
                        .iter()
                        .filter(|u| {
                            u.status
                                == glmbar_lib::providers::models::ProviderStatus::Ok
                                && !u.windows.is_empty()
                        })
                        .map(|u| u.windows[0].used_percent)
                        .collect();
                    let avg = if percents.is_empty() {
                        None
                    } else {
                        Some(percents.iter().sum::<f64>() / percents.len() as f64)
                    };

                    // Update tray icon only if percentage changed
                    let rounded = avg.map(|v| (v * 10.0).round() / 10.0);
                    if rounded != last_avg {
                        let icon_bytes = tray::create_usage_icon(rounded);
                        if let Ok(icon) = tauri::image::Image::from_bytes(&icon_bytes) {
                            if let Some(tray) = app_handle.tray_by_id("main") {
                                tray.set_icon(Some(icon)).ok();
                            }
                        }
                        last_avg = rounded;
                    }

                    // Update tooltip
                    let tooltip_lines: Vec<String> = results
                        .iter()
                        .filter(|u| {
                            u.status
                                != glmbar_lib::providers::models::ProviderStatus::NoApiKey
                        })
                        .map(|u| {
                            let summary = if u.windows.is_empty() {
                                match u.status {
                                    glmbar_lib::providers::models::ProviderStatus::Error => {
                                        "错误".into()
                                    }
                                    glmbar_lib::providers::models::ProviderStatus::Unauthorized => "认证失败".into(),
                                    _ => "暂无数据".into(),
                                }
                            } else {
                                format!("{:.0}%", u.windows[0].used_percent)
                            };
                            format!("{}: {}", u.provider_name, summary)
                        })
                        .collect();
                    let tooltip = if tooltip_lines.is_empty() {
                        "GlmBar - 请配置 API 密钥".into()
                    } else {
                        tooltip_lines.join("\n")
                    };
                    if let Some(tray) = app_handle.tray_by_id("main") {
                        tray.set_tooltip(Some(&tooltip)).ok();
                    }

                    // Emit to frontend
                    let _ = app_handle.emit("usage-updated", &results);
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|_app_handle, event| {
            if let RunEvent::ExitRequested { api, .. } = event {
                api.prevent_exit();
            }
        });
}

fn toggle_popup_window(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("popup") {
        if window.is_visible().unwrap_or(false) {
            let _ = window.hide();
        } else {
            position_popup(&window);
            let _ = window.show();
            let _ = window.set_focus();
            // Trigger refresh
            let _ = app.emit("trigger-refresh", ());
        }
    }
}

fn position_popup(window: &tauri::WebviewWindow) {
    use tauri::PhysicalPosition;
    if let Ok(monitor) = window.primary_monitor() {
        if let Some(m) = monitor {
            let size = window.inner_size().unwrap_or(tauri::PhysicalSize::new(420, 400));
            let x = m.size().width as i32 - size.width as i32 - 16;
            let y = m.size().height as i32 - size.height as i32 - 60;
            let _ = window.set_position(PhysicalPosition::new(x, y));
        }
    }
}
