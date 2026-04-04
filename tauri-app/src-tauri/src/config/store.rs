use crate::config::models::AppConfig;
use std::fs;
use std::path::PathBuf;

fn config_dir() -> PathBuf {
    let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
    home.join(".glmbar")
}

fn config_file() -> PathBuf {
    config_dir().join("config.json")
}

pub fn load_config() -> AppConfig {
    let path = config_file();
    if path.exists() {
        match fs::read_to_string(&path) {
            Ok(content) => match serde_json::from_str(&content) {
                Ok(config) => return config,
                Err(e) => {
                    eprintln!("Failed to parse config: {}", e);
                }
            },
            Err(e) => {
                eprintln!("Failed to read config: {}", e);
            }
        }
    }
    let config = AppConfig::default();
    save_config(&config);
    config
}

pub fn save_config(config: &AppConfig) {
    let dir = config_dir();
    let _ = fs::create_dir_all(&dir);
    let path = config_file();
    match serde_json::to_string_pretty(config) {
        Ok(json) => {
            if let Err(e) = fs::write(&path, json) {
                eprintln!("Failed to write config: {}", e);
            }
        }
        Err(e) => {
            eprintln!("Failed to serialize config: {}", e);
        }
    }
}
