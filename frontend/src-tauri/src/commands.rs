//! Tauri IPC 命令 —— 前端通过 invoke 调用这些函数
//!
//! 这些命令暴露给 Vue3 前端，用于：
//!   - 查询后端端口
//!   - 查询后端状态
//!   - 重启后端
//!   - 打开外部浏览器

use crate::backend::BackendManager;
use serde::Serialize;
use std::collections::VecDeque;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::sync::Mutex;
use tauri::{Manager, State};

/// 获取后端端口号（前端需要这个来构造 API 请求地址）
#[tauri::command]
pub fn get_backend_port(port: State<'_, Mutex<u16>>) -> Result<u16, String> {
    let p = port.lock().map_err(|e| e.to_string())?;
    Ok(*p)
}

/// 获取后端运行状态
#[tauri::command]
pub fn get_backend_status(
    manager: State<'_, Mutex<BackendManager>>,
) -> Result<BackendStatus, String> {
    let mgr = manager.lock().map_err(|e| e.to_string())?;
    Ok(BackendStatus {
        running: mgr.is_running(),
        port: mgr.get_port(),
    })
}

#[tauri::command]
pub fn get_service_overview(
    manager: State<'_, Mutex<BackendManager>>,
) -> Result<ServiceOverview, String> {
    let mgr = manager.lock().map_err(|e| e.to_string())?;
    let backend_running = mgr.is_running();
    let backend_port = mgr.get_port();
    let backend_origin = if backend_port > 0 {
        Some(format!("http://127.0.0.1:{}", backend_port))
    } else {
        None
    };

    Ok(ServiceOverview {
        backend: ManagedServiceStatus {
            id: "backend".to_string(),
            label: "Backend API".to_string(),
            running: backend_running,
            port: Some(backend_port),
            url: backend_origin.clone().map(|origin| format!("{}/health", origin)),
            detail: if backend_running {
                "Python/FastAPI 服务已启动，可处理接口和任务调度。".to_string()
            } else {
                "后端未运行，浏览器端将无法访问核心功能。".to_string()
            },
        },
        frontend: ManagedServiceStatus {
            id: "frontend".to_string(),
            label: "Web Portal".to_string(),
            running: backend_running,
            port: Some(backend_port),
            url: backend_origin,
            detail: if backend_running {
                "浏览器访问入口已可用，首页由本地服务提供。".to_string()
            } else {
                "浏览器入口依赖本地服务，需先恢复后端。".to_string()
            },
        },
    })
}

/// 重启后端
#[tauri::command]
pub async fn restart_backend(
    manager: State<'_, Mutex<BackendManager>>,
    port_state: State<'_, Mutex<u16>>,
) -> Result<u16, String> {
    // 先停旧的
    {
        let mgr = manager.lock().map_err(|e| e.to_string())?;
        mgr.terminate();
    }
    // 给一点时间释放端口
    tokio::time::sleep(std::time::Duration::from_secs(2)).await;

    // 再启动新的
    let mut mgr = manager.lock().map_err(|e| e.to_string())?;
    match mgr.start_and_wait(120) {
        Ok(new_port) => {
            *port_state.lock().unwrap() = new_port;
            Ok(new_port)
        }
        Err(e) => Err(e),
    }
}

#[tauri::command]
pub async fn restart_service(
    service_id: String,
    manager: State<'_, Mutex<BackendManager>>,
    port_state: State<'_, Mutex<u16>>,
) -> Result<ServiceActionResult, String> {
    match service_id.as_str() {
        "backend" | "frontend" => {
            {
                let mgr = manager.lock().map_err(|e| e.to_string())?;
                mgr.terminate();
            }
            tokio::time::sleep(std::time::Duration::from_secs(2)).await;

            let mut mgr = manager.lock().map_err(|e| e.to_string())?;
            let new_port = mgr.start_and_wait(120)?;
            *port_state.lock().unwrap() = new_port;

            Ok(ServiceActionResult {
                service_id,
                running: true,
                port: Some(new_port),
                url: Some(format!("http://127.0.0.1:{}", new_port)),
                message: "服务已重启".to_string(),
            })
        }
        other => Err(format!("不支持的服务: {}", other)),
    }
}

#[tauri::command]
pub async fn start_service(
    service_id: String,
    manager: State<'_, Mutex<BackendManager>>,
    port_state: State<'_, Mutex<u16>>,
) -> Result<ServiceActionResult, String> {
    match service_id.as_str() {
        "backend" | "frontend" => {
            let mut mgr = manager.lock().map_err(|e| e.to_string())?;
            if mgr.is_running() {
                let port = mgr.get_port();
                return Ok(ServiceActionResult {
                    service_id,
                    running: true,
                    port: Some(port),
                    url: Some(format!("http://127.0.0.1:{}", port)),
                    message: "服务已在运行".to_string(),
                });
            }

            let new_port = mgr.start_and_wait(120)?;
            *port_state.lock().unwrap() = new_port;

            Ok(ServiceActionResult {
                service_id,
                running: true,
                port: Some(new_port),
                url: Some(format!("http://127.0.0.1:{}", new_port)),
                message: "服务已启动".to_string(),
            })
        }
        other => Err(format!("不支持的服务: {}", other)),
    }
}

#[tauri::command]
pub fn stop_service(
    service_id: String,
    manager: State<'_, Mutex<BackendManager>>,
    port_state: State<'_, Mutex<u16>>,
) -> Result<ServiceActionResult, String> {
    match service_id.as_str() {
        "backend" | "frontend" => {
            let mgr = manager.lock().map_err(|e| e.to_string())?;
            mgr.terminate();
            *port_state.lock().unwrap() = 0;

            Ok(ServiceActionResult {
                service_id,
                running: false,
                port: None,
                url: None,
                message: "服务已停止".to_string(),
            })
        }
        other => Err(format!("不支持的服务: {}", other)),
    }
}

/// 在系统浏览器中打开 URL
#[tauri::command]
pub fn open_in_browser(url: String) -> Result<(), String> {
    webbrowser::open(&url).map_err(|e| format!("打开浏览器失败: {}", e))
}

/// 运行安装流程
#[tauri::command]
pub fn run_installation(
    manager: State<'_, Mutex<BackendManager>>,
) -> Result<InstallationStatus, String> {
    let mgr = manager.lock().map_err(|e| e.to_string())?;
    
    // 检查是否需要安装
    let python_path = mgr.find_python();
    let needs_install = python_path.is_none();
    
    // 尝试提取内嵌 Python
    let embedded_extracted = if needs_install {
        if let Ok(resource_dir) = mgr._app_handle.path().resource_dir() {
            let zip_path = resource_dir.join("python-3.11.9-embed-amd64.zip");
            if zip_path.exists() {
                let target_python = mgr.project_root.join("tools/python_embed/python.exe");
                mgr.extract_python_from_zip(&zip_path, &target_python).is_ok()
            } else {
                false
            }
        } else {
            false
        }
    } else {
        true
    };
    
    Ok(InstallationStatus {
        needs_install: !embedded_extracted,
        python_available: python_path.is_some() || embedded_extracted,
        embedded_extracted,
        python_path: python_path.map(|p| p.to_string_lossy().to_string()),
    })
}

/// 检查环境状态
#[tauri::command]
pub fn check_environment(
    manager: State<'_, Mutex<BackendManager>>,
) -> Result<EnvironmentInfo, String> {
    let mgr = manager.lock().map_err(|e| e.to_string())?;
    
    let python_available = mgr.find_python().is_some();
    let has_embedded = {
        if let Ok(resource_dir) = mgr._app_handle.path().resource_dir() {
            resource_dir.join("python-3.11.9-embed-amd64.zip").exists() ||
            resource_dir.join("python_embed").exists()
        } else {
            false
        }
    };
    
    let project_root = mgr.project_root.to_string_lossy().to_string();
    
    Ok(EnvironmentInfo {
        python_available,
        has_embedded_python: has_embedded,
        project_root,
    })
}

/// 手动提取内嵌 Python
#[tauri::command]
pub fn extract_embedded_python(
    manager: State<'_, Mutex<BackendManager>>,
) -> Result<bool, String> {
    let mgr = manager.lock().map_err(|e| e.to_string())?;
    
    if let Ok(resource_dir) = mgr._app_handle.path().resource_dir() {
        let zip_path = resource_dir.join("python-3.11.9-embed-amd64.zip");
        let target_python = mgr.project_root.join("tools/python_embed/python.exe");
        
        if zip_path.exists() {
            match mgr.extract_python_from_zip(&zip_path, &target_python) {
                Ok(()) => Ok(true),
                Err(e) => Err(e),
            }
        } else {
            Err("未找到内嵌 Python zip 文件".to_string())
        }
    } else {
        Err("无法访问资源目录".to_string())
    }
}

#[tauri::command]
pub fn get_runtime_logs(
    manager: State<'_, Mutex<BackendManager>>,
    lines: Option<usize>,
) -> Result<RuntimeLogSnapshot, String> {
    let mgr = manager.lock().map_err(|e| e.to_string())?;
    let log_path = mgr.resolve_runtime_log_file_path();
    let requested_lines = lines.unwrap_or(200).clamp(20, 1000);

    if !log_path.exists() {
        return Ok(RuntimeLogSnapshot {
            path: log_path.to_string_lossy().to_string(),
            exists: false,
            line_count: 0,
            lines: vec![],
        });
    }

    let file = File::open(&log_path)
        .map_err(|e| format!("打开日志文件失败 {}: {}", log_path.display(), e))?;
    let reader = BufReader::new(file);
    let mut ring = VecDeque::with_capacity(requested_lines);
    let mut total_count = 0usize;

    for line in reader.lines() {
        let line = line.map_err(|e| format!("读取日志文件失败 {}: {}", log_path.display(), e))?;
        total_count += 1;
        if ring.len() == requested_lines {
            ring.pop_front();
        }
        ring.push_back(line);
    }

    Ok(RuntimeLogSnapshot {
        path: log_path.to_string_lossy().to_string(),
        exists: true,
        line_count: total_count,
        lines: ring.into_iter().collect(),
    })
}

/// 后端状态返回结构
#[derive(serde::Serialize, Clone)]
pub struct BackendStatus {
    running: bool,
    port: u16,
}

#[derive(Serialize, Clone)]
pub struct ManagedServiceStatus {
    id: String,
    label: String,
    running: bool,
    port: Option<u16>,
    url: Option<String>,
    detail: String,
}

#[derive(Serialize, Clone)]
pub struct ServiceOverview {
    backend: ManagedServiceStatus,
    frontend: ManagedServiceStatus,
}

#[derive(Serialize, Clone)]
pub struct ServiceActionResult {
    service_id: String,
    running: bool,
    port: Option<u16>,
    url: Option<String>,
    message: String,
}

#[derive(Serialize, Clone)]
pub struct RuntimeLogSnapshot {
    path: String,
    exists: bool,
    line_count: usize,
    lines: Vec<String>,
}

/// 安装状态返回结构
#[derive(serde::Serialize, Clone)]
pub struct InstallationStatus {
    needs_install: bool,
    python_available: bool,
    embedded_extracted: bool,
    python_path: Option<String>,
}

/// 环境信息返回结构
#[derive(serde::Serialize, Clone)]
pub struct EnvironmentInfo {
    python_available: bool,
    has_embedded_python: bool,
    project_root: String,
}
