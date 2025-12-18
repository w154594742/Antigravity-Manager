use axum::{
    Router,
    routing::{get, post},
    extract::State,
    response::{IntoResponse, Response, sse::{Event, Sse}},
    http::StatusCode,
    Json,
};
use std::sync::Arc;
use tokio::sync::oneshot;
use futures::stream::StreamExt;
use crate::proxy::{TokenManager, converter, client::GeminiClient};

/// Axum 应用状态
#[derive(Clone)]
pub struct AppState {
    pub token_manager: Arc<TokenManager>,
    pub anthropic_mapping: Arc<std::collections::HashMap<String, String>>,
    pub request_timeout: u64,  // API 请求超时(秒)
}

/// Axum 服务器实例
pub struct AxumServer {
    shutdown_tx: Option<oneshot::Sender<()>>,
}

impl AxumServer {
    /// 启动 Axum 服务器
    pub async fn start(
        port: u16,
        token_manager: Arc<TokenManager>,
        anthropic_mapping: std::collections::HashMap<String, String>,
        request_timeout: u64,  // 新增超时参数
    ) -> Result<(Self, tokio::task::JoinHandle<()>), String> {
        let state = AppState {
            token_manager,
            anthropic_mapping: Arc::new(anthropic_mapping),
            request_timeout,
        };
        
        // 构建路由
        let app = Router::new()
            .route("/v1/chat/completions", post(chat_completions_handler))
            .route("/v1/messages", post(anthropic_messages_handler))
            .route("/v1/models", get(list_models_handler))
            .route("/healthz", get(health_check_handler))
            .with_state(state);
        
        // 绑定地址
        let addr = format!("127.0.0.1:{}", port);
        let listener = tokio::net::TcpListener::bind(&addr)
            .await
            .map_err(|e| format!("端口 {} 绑定失败: {}", port, e))?;
        
        tracing::info!("反代服务器启动在 http://{}", addr);
        
        // 创建关闭通道
        let (shutdown_tx, shutdown_rx) = oneshot::channel::<()>();
        
        // 在新任务中启动服务器
        let handle = tokio::spawn(async move {
            axum::serve(listener, app)
                .with_graceful_shutdown(async {
                    shutdown_rx.await.ok();
                })
                .await
                .ok();
        });
        
        Ok((
            Self {
                shutdown_tx: Some(shutdown_tx),
            },
            handle,
        ))
    }
    
    /// 停止服务器
    pub fn stop(mut self) {
        if let Some(tx) = self.shutdown_tx.take() {
            let _ = tx.send(());
        }
    }
}

// ===== API 处理器 =====

/// 请求处理结果
enum RequestResult {
    Success(Response),
    Retry(String), // 包含重试原因
    Error(Response),
}

/// 聊天补全处理器
async fn chat_completions_handler(
    State(state): State<AppState>,
    Json(request): Json<converter::OpenAIChatRequest>,
) -> Response {
    let max_retries = state.token_manager.len().max(1);
    let mut attempts = 0;
    
    // 克隆请求以支持重试
    let request = Arc::new(request);

    loop {
        attempts += 1;
        
        // 1. 获取 Token
        let token = match state.token_manager.get_token().await {
            Some(t) => t,
            None => {
                return (
                    StatusCode::SERVICE_UNAVAILABLE,
                    Json(serde_json::json!({
                        "error": {
                            "message": "没有可用账号",
                            "type": "no_accounts"
                        }
                    }))
                ).into_response();
            }
        };
        
        tracing::info!("尝试使用账号: {} (第 {}/{} 次尝试)", token.email, attempts, max_retries);

        // 2. 处理请求
        let result = process_request(state.clone(), request.clone(), token.clone()).await;
        
        match result {
            RequestResult::Success(response) => return response,
            RequestResult::Retry(reason) => {
                tracing::warn!("账号 {} 请求失败，准备重试: {}", token.email, reason);
                if attempts >= max_retries {
                    return (
                        StatusCode::TOO_MANY_REQUESTS,
                        Json(serde_json::json!({
                            "error": {
                                "message": format!("所有账号配额已耗尽或请求失败。最后错误: {}", reason),
                                "type": "all_accounts_exhausted"
                            }
                        }))
                    ).into_response();
                }
                // 继续下一次循环，token_manager.get_token() 会自动轮换
                continue;
            },
            RequestResult::Error(response) => return response,
        }
    }
}

/// 统一请求分发入口
async fn process_request(
    state: AppState,
    request: Arc<converter::OpenAIChatRequest>,
    token: crate::proxy::token_manager::ProxyToken,
) -> RequestResult {
    let is_stream = request.stream.unwrap_or(false);
    let is_image_model = request.model.contains("gemini-3-pro-image");
    
    if is_stream {
        if is_image_model {
            handle_image_stream_request(state, request, token).await
        } else {
            handle_stream_request(state, request, token).await
        }
    } else {
        handle_non_stream_request(state, request, token).await
    }
}

/// 处理画图模型的流式请求（模拟流式）
async fn handle_image_stream_request(
    state: AppState,
    request: Arc<converter::OpenAIChatRequest>,
    token: crate::proxy::token_manager::ProxyToken,
) -> RequestResult {
    let client = GeminiClient::new(state.request_timeout);
    let model = request.model.clone();
    
    let project_id = match get_project_id(&token) {
        Ok(id) => id,
        Err(e) => return RequestResult::Error(e),
    };
    
    let response_result = client.generate(
        &request,
        &token.access_token,
        project_id,
        &token.session_id,
    ).await;
    
    match response_result {
        Ok(response) => {
            // 2. 处理图片转 Markdown
            let processed_json = process_inline_data(response);
            
            // 3. 提取 Markdown 文本
            // 移除详细调试日志以免刷屏
            // tracing::info!("Processed Image Response: {}", serde_json::to_string_pretty(&processed_json).unwrap_or_default());
            tracing::info!("Image generation successful, processing response...");

            let content = processed_json["response"]["candidates"][0]["content"]["parts"][0]["text"]
                .as_str()
                .or_else(|| {
                    // 尝试备用路径：有时候 structure 可能略有不同
                    tracing::warn!("Standard path for image content failed. Checking response structure...");
                    processed_json["candidates"][0]["content"]["parts"][0]["text"].as_str()
                })
                .unwrap_or("生成图片失败或格式错误")
                .to_string();
                
            // 4. 构造 SSE 流
            let stream = async_stream::stream! {
                let chunk = serde_json::json!({
                    "id": format!("chatcmpl-{}", uuid::Uuid::new_v4()),
                    "object": "chat.completion.chunk",
                    "created": chrono::Utc::now().timestamp(),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": { "content": content },
                            "finish_reason": null
                        }
                    ]
                });
                yield Ok::<_, axum::Error>(Event::default().data(chunk.to_string()));
                
                let end_chunk = serde_json::json!({
                    "id": format!("chatcmpl-{}", uuid::Uuid::new_v4()),
                    "object": "chat.completion.chunk",
                    "created": chrono::Utc::now().timestamp(),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }
                    ]
                });
                yield Ok(Event::default().data(end_chunk.to_string()));
                yield Ok(Event::default().data("[DONE]"));
            };
            
            RequestResult::Success(Sse::new(stream).into_response())
        },
        Err(e) => check_retry_error(&e),
    }
}

/// 处理流式请求
async fn handle_stream_request(
    state: AppState,
    request: Arc<converter::OpenAIChatRequest>,
    token: crate::proxy::token_manager::ProxyToken,
) -> RequestResult {
    let client = GeminiClient::new(state.request_timeout);
    
    let project_id = match get_project_id(&token) {
        Ok(id) => id,
        Err(e) => return RequestResult::Error(e),
    };
    
    let stream_result = client.stream_generate(
        &request,
        &token.access_token,
        project_id,
        &token.session_id,
    ).await;
    
    match stream_result {
        Ok(stream) => {
            let sse_stream = stream.map(move |chunk| {
                match chunk {
                    Ok(data) => Ok(Event::default().data(data)),
                    Err(e) => {
                        tracing::error!("Stream error: {}", e);
                        Err(axum::Error::new(e))
                    }
                }
            });
            RequestResult::Success(Sse::new(sse_stream).into_response())
        },
        Err(e) => check_retry_error(&e),
    }
}

/// 处理非流式请求
async fn handle_non_stream_request(
    state: AppState,
    request: Arc<converter::OpenAIChatRequest>,
    token: crate::proxy::token_manager::ProxyToken,
) -> RequestResult {
    let client = GeminiClient::new(state.request_timeout);
    
    let project_id = match get_project_id(&token) {
        Ok(id) => id,
        Err(e) => return RequestResult::Error(e),
    };
    
    let response_result = client.generate(
        &request,
        &token.access_token,
        project_id,
        &token.session_id,
    ).await;
    
    match response_result {
        Ok(response) => {
            let processed_response = process_inline_data(response);
            RequestResult::Success(Json(processed_response).into_response())
        },
        Err(e) => check_retry_error(&e),
    }
}

/// 辅助函数：获取 Project ID
fn get_project_id(token: &crate::proxy::token_manager::ProxyToken) -> Result<&str, Response> {
    token.project_id.as_ref()
        .map(|s| s.as_str())
        .ok_or_else(|| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({
                    "error": {
                        "message": "没有 project_id",
                        "type": "config_error"
                    }
                }))
            ).into_response()
        })
}

/// 辅助函数：检查错误是否需要重试
fn check_retry_error(error_msg: &str) -> RequestResult {
    // 检查 429 或者 配额耗尽 关键字
    if error_msg.contains("429") || 
       error_msg.contains("RESOURCE_EXHAUSTED") || 
       error_msg.contains("QUOTA_EXHAUSTED") ||
       error_msg.contains("The request has been rate limited") ||
       // 新增：网络错误或响应解析失败也进行重试
       error_msg.contains("读取响应文本失败") ||
       error_msg.contains("error decoding response body") ||
       error_msg.contains("closed connection") ||
       error_msg.contains("error sending request") ||
       error_msg.contains("operation timed out") {
        return RequestResult::Retry(error_msg.to_string());
    }
    
    // 其他错误直接返回
    RequestResult::Error((
        StatusCode::INTERNAL_SERVER_ERROR,
        Json(serde_json::json!({
            "error": {
                "message": format!("Antigravity API 错误: {}", error_msg),
                "type": "api_error"
            }
        }))
    ).into_response())
}

/// 模型列表处理器
async fn list_models_handler(
    State(_state): State<AppState>,
) -> Response {
    // 返回 Antigravity 实际可用的模型列表
    let models = serde_json::json!({
        "object": "list",
        "data": [
            {
                "id": "gemini-2.5-flash",
                "object": "model",
                "created": 1734336000,
                "owned_by": "google"
            },
            {
                "id": "gemini-3-pro-low",
                "object": "model",
                "created": 1734336000,
                "owned_by": "google"
            },
            {
                "id": "gemini-3-pro-high",
                "object": "model",
                "created": 1734336000,
                "owned_by": "google"
            },
            {
                "id": "gemini-3-pro-image",
                "object": "model",
                "created": 1734336000,
                "owned_by": "google"
            },
            {
                "id": "gemini-3-pro-image-16x9",
                "object": "model",
                "created": 1734336000,
                "owned_by": "google"
            },
            {
                "id": "gemini-3-pro-image-9x16",
                "object": "model",
                "created": 1734336000,
                "owned_by": "google"
            },
            {
                "id": "gemini-3-pro-image-4k",
                "object": "model",
                "created": 1734336000,
                "owned_by": "google"
            },
            {
                "id": "claude-sonnet-4-5",
                "object": "model",
                "created": 1734336000,
                "owned_by": "anthropic"
            },
            {
                "id": "claude-sonnet-4-5-thinking",
                "object": "model",
                "created": 1734336000,
                "owned_by": "anthropic"
            },
            {
                "id": "claude-opus-4-5-thinking",
                "object": "model",
                "created": 1734336000,
                "owned_by": "anthropic"
            },
            {
                "id": "gemini-2.5-flash-thinking",
                "object": "model",
                "created": 1734336000,
                "owned_by": "google"
            }
        ]
    });
    
    Json(models).into_response()
}

/// 健康检查处理器
async fn health_check_handler() -> Response {
    Json(serde_json::json!({
        "status": "ok"
    })).into_response()
}

/// 处理 Antigravity 响应中的 inlineData(生成的图片)
/// 将 base64 图片转换为 Markdown 格式
/// 处理 Inline Data (base64 图片) 转 Markdown
fn process_inline_data(mut response: serde_json::Value) -> serde_json::Value {
    // 1. 定位 candidates 节点
    // Antigravity 响应可能是 { "candidates": ... } 或 { "response": { "candidates": ... } }
    let candidates_node = if response.get("candidates").is_some() {
        response.get_mut("candidates")
    } else if let Some(r) = response.get_mut("response") {
         r.get_mut("candidates")
    } else {
        None
    };

    if let Some(candidates_val) = candidates_node {
        if let Some(candidates) = candidates_val.as_array_mut() {
            for candidate in candidates {
                if let Some(content) = candidate["content"].as_object_mut() {
                    if let Some(parts) = content["parts"].as_array_mut() {
                        let mut new_parts = Vec::new();
                        
                        for part in parts.iter() {
                            // 检查是否有 inlineData
                            if let Some(inline_data) = part.get("inlineData") {
                                let mime_type = inline_data["mimeType"]
                                    .as_str()
                                    .unwrap_or("image/jpeg");
                                let data = inline_data["data"]
                                    .as_str()
                                    .unwrap_or("");
                                
                                // 构造 Markdown 图片语法
                                let image_markdown = format!(
                                    "\n\n![Generated Image](data:{};base64,{})\n\n",
                                    mime_type, data
                                );
                                
                                // 替换为文本 part
                                new_parts.push(serde_json::json!({
                                    "text": image_markdown
                                }));
                            } else {
                                // 保留原始 part
                                new_parts.push(part.clone());
                            }
                        }
                        
                        // 更新 parts
                        *parts = new_parts;
                    }
                }
            }
        }
    }
    
    // 直接返回修改后的对象，不再包裹 "response"
    response
}

/// Anthropic Messages 处理器
async fn anthropic_messages_handler(
    State(state): State<AppState>,
    Json(request): Json<converter::AnthropicChatRequest>,
) -> Response {
    // 记录请求信息
    let stream_mode = request.stream.unwrap_or(true);
    let msg_count = request.messages.len();
    let first_msg_preview = if let Some(first_msg) = request.messages.first() {
        // content 是 Vec<AnthropicContent>
        if let Some(first_content) = first_msg.content.first() {
            match first_content {
                converter::AnthropicContent::Text { text } => {
                    if text.len() > 50 {
                        format!("{}...", &text[..50])
                    } else {
                        text.clone()
                    }
                },
                converter::AnthropicContent::Image { .. } => {
                    "[图片]".to_string()
                }
            }
        } else {
            "无内容".to_string()
        }
    } else {
        "无消息".to_string()
    };
    
    // 预处理：解析映射后的模型名（仅用于日志显示，实际逻辑在 client 中也会再次处理，或者我们可以这里处理完传进去）
    // 为了保持一致性，我们复用简单的查找逻辑用于日志
    let mapped_model = {
        let mapping = &state.anthropic_mapping;
        if let Some(m) = mapping.get(&request.model) {
            m.clone()
        } else {
            // 简单模糊匹配
            let mut m = request.model.clone();
            for (k, v) in mapping.iter() {
                if request.model.contains(k) {
                    m = v.clone();
                    break;
                }
            }
            // 默认回退逻辑 (与 Client 保持一致)
            if m == request.model {
                if request.model.contains("claude") {
                    if request.model.contains("sonnet") { "gemini-3-pro-high".to_string() } else { "gemini-3-pro-low".to_string() }
                } else {
                    m
                }
            } else {
                m
            }
        }
    };

    // 截断过长的消息预览
    let truncated_preview = if first_msg_preview.len() > 50 {
        format!("{}...", &first_msg_preview[..50])
    } else {
        first_msg_preview.clone()
    };
    
    tracing::info!(
        "(Anthropic) 请求 {} → {} | 消息数:{} | 流式:{} | 预览:{}",
        request.model,
        mapped_model,
        msg_count,
        if stream_mode { "是" } else { "否" },
        truncated_preview
    );
    let max_retries = state.token_manager.len().max(1);
    let mut attempts = 0;
    
    // Check if stream is requested. Default to false? Anthropic usually true for interactive.
    let is_stream = request.stream.unwrap_or(false);
    
    // Clone request for retries
    let request = Arc::new(request);

    loop {
        attempts += 1;
        
        // 1. 获取 Token
        let token = match state.token_manager.get_token().await {
            Some(t) => t,
            None => {
                 return (
                    StatusCode::SERVICE_UNAVAILABLE,
                    Json(serde_json::json!({
                        "type": "error",
                        "error": {
                            "type": "overloaded_error",
                            "message": "No available accounts"
                        }
                    }))
                ).into_response();
            }
        };
        
        tracing::info!("(Anthropic) 尝试使用账号: {} (第 {}/{} 次尝试)", token.email, attempts, max_retries);

        // 2. 发起请求
        // Helper logic inline to support retries
        let client = GeminiClient::new(state.request_timeout);
        let project_id_result = get_project_id(&token);
        
        if let Err(e) = project_id_result {
             // If config error, don't retry, just fail
             return e; // e is Response
        }
        let project_id = project_id_result.unwrap();

        if is_stream {
             let stream_result = client.stream_generate_anthropic(
                &request,
                &token.access_token,
                project_id,
                &token.session_id,
                &state.anthropic_mapping
            ).await;
            
            match stream_result {
                Ok(stream) => {
                    // Success! Convert stream to Anthropic SSE
                    // Setup header for SSE
                    let msg_id = format!("msg_{}", uuid::Uuid::new_v4());
                    let token_clone = token.clone();
                    let mut total_content = String::new(); // 收集完整内容用于日志
                    let model_name = request.model.clone();
                    
                    // SSE processing Logic
                     let sse_stream = async_stream::stream! {
                        // 1. send message_start
                        let start_event_json = serde_json::json!({
                            "type": "message_start",
                            "message": {
                                "id": msg_id,
                                "type": "message",
                                "role": "assistant",
                                "model": model_name,
                                "content": [],
                                "stop_reason": null,
                                "stop_sequence": null,
                                "usage": { "input_tokens": 0, "output_tokens": 0 } // Dummy usage
                            }
                        });
                        yield Ok::<_, axum::Error>(Event::default().event("message_start").data(start_event_json.to_string()));

                        // 2. send content_block_start
                        let block_start_json = serde_json::json!({
                            "type": "content_block_start",
                            "index": 0,
                            "content_block": {
                                "type": "text",
                                "text": ""
                            }
                        });
                         yield Ok(Event::default().event("content_block_start").data(block_start_json.to_string()));
                         
                        // 3. Loop over chunks (which are OpenAI chunks from client)
                        for await chunk_result in stream {
                            match chunk_result {
                                Ok(chunk_str) => {
                                    if chunk_str == "[DONE]" { continue; }
                                    
                                    // Parse OpenAI Chunk
                                    if let Ok(json) = serde_json::from_str::<serde_json::Value>(&chunk_str) {
                                        let delta_content = json["choices"][0]["delta"]["content"].as_str().unwrap_or("");
                                        let finish_reason = json["choices"][0]["finish_reason"].as_str();

                                        if !delta_content.is_empty() {
                                            total_content.push_str(delta_content);
                                            let delta_json = serde_json::json!({
                                                "type": "content_block_delta",
                                                "index": 0,
                                                "delta": {
                                                    "type": "text_delta",
                                                    "text": delta_content
                                                }
                                            });
                                            yield Ok(Event::default().event("content_block_delta").data(delta_json.to_string()));
                                        }
                                        
                                        if let Some(reason) = finish_reason {
                                            // Send message_delta with stop reason
                                            let stop_reason = match reason {
                                                "stop" => "end_turn",
                                                "length" => "max_tokens",
                                                _ => "end_turn"
                                            };
                                            
                                            let msg_delta_json = serde_json::json!({
                                                "type": "message_delta",
                                                "delta": {
                                                    "stop_reason": stop_reason,
                                                    "stop_sequence": null,
                                                    "usage": { "output_tokens": 0 }
                                                }
                                            });
                                            yield Ok(Event::default().event("message_delta").data(msg_delta_json.to_string()));
                                            
                                            // Send message_stop
                                            let stop_json = serde_json::json!({"type": "message_stop"});
                                            yield Ok(Event::default().event("message_stop").data(stop_json.to_string()));
                                            
                                            // 记录响应完成及内容
                                            if total_content.is_empty() {
                                                tracing::warn!(
                                                    "(Anthropic) ✓ {} | 回答为空 (可能是 Gemini 返回了非文本数据)",
                                                    token_clone.email
                                                );
                                            } else {
                                                let preview_len = total_content.len().min(100);  // 增加到 100 字符
                                                let response_preview = &total_content[..preview_len];
                                                let suffix = if total_content.len() > 100 { "..." } else { "" };
                                                
                                                tracing::info!(
                                                    "(Anthropic) ✓ {} | 回答: {}{}",
                                                    token_clone.email,
                                                    response_preview,
                                                    suffix
                                                );
                                            }
                                        }
                                    }
                                }
                                Err(_) => {
                                     // logging done in client
                                }
                            }
                        }
                    };
                    
                    return Sse::new(sse_stream).into_response();
                },
                Err(e_msg) => {
                    // Check retry
                    let check = check_retry_error(&e_msg);
                    match check {
                        RequestResult::Retry(reason) => {
                            tracing::warn!("(Anthropic) 账号 {} 请求失败，重试: {}", token.email, reason);
                             if attempts >= max_retries {
                                 return (
                                    StatusCode::TOO_MANY_REQUESTS,
                                    Json(serde_json::json!({
                                        "type": "error",
                                        "error": {
                                            "type": "rate_limit_error",
                                            "message": format!("Max retries exceeded. Last error: {}", reason)
                                        }
                                    }))
                                ).into_response();
                             }
                             continue;
                        },
                        RequestResult::Error(resp) => return resp,
                        RequestResult::Success(resp) => return resp, // Should not happen here
                    }
                }
            }

        } else {
            // Non-stream: collect streaming response and convert to non-streaming format
            let stream_result = client.stream_generate_anthropic(
                &request,
                &token.access_token,
                project_id,
                &token.session_id,
                &state.anthropic_mapping
            ).await;
            
            match stream_result {
                Ok(mut stream) => {
                    let mut full_text = String::new();
                    let mut stop_reason = "end_turn";
                    
                    // Collect all chunks
                    while let Some(chunk_result) = stream.next().await {
                        match chunk_result {
                            Ok(chunk_str) => {
                                if chunk_str == "[DONE]" { continue; }
                                
                                if let Ok(json) = serde_json::from_str::<serde_json::Value>(&chunk_str) {
                                    if let Some(content) = json["choices"][0]["delta"]["content"].as_str() {
                                        full_text.push_str(content);
                                    }
                                    if let Some(reason) = json["choices"][0]["finish_reason"].as_str() {
                                        stop_reason = match reason {
                                            "stop" => "end_turn",
                                            "length" => "max_tokens",
                                            _ => "end_turn"
                                        };
                                    }
                                }
                            }
                            Err(_) => {}
                        }
                    }
                    
                    // Build Anthropic non-streaming response
                    let response = serde_json::json!({
                        "id": format!("msg_{}", uuid::Uuid::new_v4()),
                        "type": "message",
                        "role": "assistant",
                        "model": request.model,
                        "content": [{
                            "type": "text",
                            "text": full_text
                        }],
                        "stop_reason": stop_reason,
                        "stop_sequence": null,
                        "usage": {
                            "input_tokens": 0,
                            "output_tokens": 0
                        }
                    });
                    
                    // 记录响应(截取前60字符)
                    let answer_text = response["content"].as_array()
                        .and_then(|arr| arr.first())
                        .and_then(|c| c["text"].as_str())
                        .unwrap_or("");
                    let preview_len = answer_text.len().min(60);
                    let answer_preview = &answer_text[..preview_len];
                    let suffix = if answer_text.len() > 60 { "..." } else { "" };
                    
                    tracing::info!(
                        "(Anthropic) ✓ {} | 回答: {}{}",
                        token.email, answer_preview, suffix
                    );
                    
                    return (StatusCode::OK, Json(response)).into_response();
                },
                Err(e_msg) => {
                    let check = check_retry_error(&e_msg);
                    match check {
                        RequestResult::Retry(reason) => {
                            tracing::warn!("(Anthropic) 账号 {} 请求失败，重试: {}", token.email, reason);
                            if attempts >= max_retries {
                                return (
                                    StatusCode::TOO_MANY_REQUESTS,
                                    Json(serde_json::json!({
                                        "type": "error",
                                        "error": {
                                            "type": "rate_limit_error",
                                            "message": format!("Max retries exceeded. Last error: {}", reason)
                                        }
                                    }))
                                ).into_response();
                            }
                            continue;
                        },
                        RequestResult::Error(resp) => return resp,
                        RequestResult::Success(resp) => return resp,
                    }
                }
            }
        }
    }
}
