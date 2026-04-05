pub mod alibaba;
pub mod baidu;
pub mod custom;
pub mod kimi;
pub mod minimax;
pub mod models;
pub mod openrouter;
pub mod zai;

use crate::config::models::ProviderConfig;
use models::UsageData;
use std::future::Future;
use std::pin::Pin;

pub trait Provider: Send + Sync {
    fn fetch_usage(&self) -> Pin<Box<dyn Future<Output = UsageData> + Send + '_>>;
}

pub fn create_provider(config: &ProviderConfig, client: &reqwest::Client) -> Box<dyn Provider> {
    match config.provider_type.as_str() {
        "zai" => Box::new(zai::ZaiProvider::new(
            client.clone(),
            &config.api_key,
            config.extra.get("region").map(|s| s.as_str()),
        )),
        "minimax" => Box::new(minimax::MiniMaxProvider::new(
            client.clone(),
            &config.api_key,
            config.extra.get("region").map(|s| s.as_str()),
        )),
        "kimi" => Box::new(kimi::KimiProvider::new(client.clone(), &config.api_key)),
        "alibaba" => Box::new(alibaba::AlibabaProvider::new(
            client.clone(),
            &config.api_key,
            config.extra.get("region").map(|s| s.as_str()),
        )),
        "openrouter" => Box::new(openrouter::OpenRouterProvider::new(client.clone(), &config.api_key)),
        "baidu" => Box::new(baidu::BaiduQianfanProvider::new(client.clone(), &config.extra)),
        _ => Box::new(custom::CustomProvider::new(
            client.clone(),
            &config.id,
            &config.name,
            &config.api_key,
            config.extra.get("quota_url").map(|s| s.as_str()),
        )),
    }
}

/// Get the display config fields for a provider type.
/// Returns a vec of (field_name, field_type) where field_type is "password", "select:opt1,opt2", "textarea", or "text".
pub fn get_display_config(provider_type: &str) -> Vec<(String, String)> {
    match provider_type {
        "zai" | "minimax" | "alibaba" => vec![
            ("api_key".into(), "password".into()),
            ("region".into(), "select:china,global".into()),
        ],
        "kimi" | "openrouter" => vec![("api_key".into(), "password".into())],
        "baidu" => vec![("curl".into(), "textarea".into())],
        _ => vec![
            ("api_key".into(), "password".into()),
            ("quota_url".into(), "text".into()),
        ],
    }
}
