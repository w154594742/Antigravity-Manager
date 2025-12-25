// OpenAI Handler
use axum::{extract::State, extract::Json, http::StatusCode, response::IntoResponse};
use serde_json::{json, Value};
use tracing::{debug, error};

use crate::proxy::mappers::openai::{transform_openai_request, transform_openai_response, OpenAIRequest};
// use crate::proxy::upstream::client::UpstreamClient; // 通过 state 获取
use crate::proxy::server::AppState;
 
const MAX_RETRY_ATTEMPTS: usize = 3;
 
pub async fn handle_chat_completions(
    State(state): State<AppState>,
    Json(body): Json<Value>
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let openai_req: OpenAIRequest = serde_json::from_value(body)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("Invalid request: {}", e)))?;

    debug!("Received OpenAI request for model: {}", openai_req.model);

    // 1. 获取 UpstreamClient (Clone handle)
    let upstream = state.upstream.clone();
    let token_manager = state.token_manager;
    let pool_size = token_manager.len();
    let max_attempts = MAX_RETRY_ATTEMPTS.min(pool_size).max(1);
    
    let mut last_error = String::new();
 
    for attempt in 0..max_attempts {
        // 2. 获取 Token
        let model_group = crate::proxy::common::utils::infer_quota_group(&openai_req.model);
        let (access_token, project_id) = match token_manager.get_token(&model_group).await {
            Ok(t) => t,
            Err(e) => {
                return Err((StatusCode::SERVICE_UNAVAILABLE, format!("Token error: {}", e)));
            }
        };

        // 3. 转换请求
        let mapped_model = crate::proxy::common::model_mapping::resolve_model_route(
            &openai_req.model,
            &*state.custom_mapping.read().await,
            &*state.openai_mapping.read().await,
            &*state.anthropic_mapping.read().await,
        );
        let gemini_body = transform_openai_request(&openai_req, &project_id, &mapped_model);

        // 4. 发送请求
        let list_response = openai_req.stream;
        let method = if list_response { "streamGenerateContent" } else { "generateContent" };
        let query_string = if list_response { Some("alt=sse") } else { None };

        let response = match upstream
            .call_v1_internal(method, &access_token, gemini_body, query_string)
            .await {
                Ok(r) => r,
                Err(e) => {
                    last_error = e.clone();
                    tracing::warn!("OpenAI Request failed on attempt {}/{}: {}", attempt + 1, max_attempts, e);
                    continue;
                }
            };

        let status = response.status();
        if status.is_success() {
            // 5. 处理流式 vs 非流式
            if list_response {
                use crate::proxy::mappers::openai::streaming::create_openai_sse_stream;
                use axum::response::Response;
                use axum::body::Body;
// Removed redundant StreamExt

                let gemini_stream = response.bytes_stream();
                let openai_stream = create_openai_sse_stream(Box::pin(gemini_stream), openai_req.model.clone());
                let body = Body::from_stream(openai_stream);

                return Ok(Response::builder()
                    .header("Content-Type", "text/event-stream")
                    .header("Cache-Control", "no-cache")
                    .header("Connection", "keep-alive")
                    .body(body)
                    .unwrap()
                    .into_response());
            }

            let gemini_resp: Value = response
                .json()
                .await
                .map_err(|e| (StatusCode::BAD_GATEWAY, format!("Parse error: {}", e)))?;

            let openai_response = transform_openai_response(&gemini_resp);
            return Ok(Json(openai_response).into_response());
        }

        // 处理特定错误并重试
        let status_code = status.as_u16();
        let error_text = response.text().await.unwrap_or_default();
        last_error = format!("HTTP {}: {}", status_code, error_text);
 
        // 只有 429 (限流), 403 (权限/地区限制) 和 401 (认证失效) 触发账号轮换
        if status_code == 429 || status_code == 403 || status_code == 401 {
            // 如果是 429 且标记为配额耗尽，直接报错，避免穿透整个账号池
            if status_code == 429 && (error_text.contains("QUOTA_EXHAUSTED") || error_text.contains("quota")) {
                error!("OpenAI Quota exhausted (429) on attempt {}/{}, stopping to protect pool.", attempt + 1, max_attempts);
                return Err((status, error_text));
            }

            tracing::warn!("OpenAI Upstream {} on attempt {}/{}, rotating account", status_code, attempt + 1, max_attempts);
            continue;
        }
 
        // 404 等由于模型配置或路径错误的 HTTP 异常，直接报错，不进行无效轮换
        error!("OpenAI Upstream non-retryable error {}: {}", status_code, error_text);
        return Err((status, error_text));
    }

    // 所有尝试均失败
    Err((StatusCode::TOO_MANY_REQUESTS, format!("All accounts exhausted. Last error: {}", last_error)))
}

pub async fn handle_list_models() -> impl IntoResponse {
    Json(json!({
        "object": "list",
        "data": [
            {"id": "gpt-4", "object": "model", "created": 1706745600, "owned_by": "openai"},
            {"id": "gpt-3.5-turbo", "object": "model", "created": 1706745600, "owned_by": "openai"},
            {"id": "o1-mini", "object": "model", "created": 1706745600, "owned_by": "openai"}
        ]
    }))
}
