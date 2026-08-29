//! DingDa 过程宏（`#[timed]` / `#[runtime]` / `apply_conn_state!`）。
//!
//! 作者：Xiaoman
//! 创建时间：2026-08-13

use proc_macro::TokenStream;
use quote::quote;
use syn::{
    parse::{Parse, ParseStream},
    parse_macro_input, Ident, ItemFn, LitStr, Token,
};

/// 为异步函数显式记录耗时日志（opt-in，按需标注，不默认用于全部 IPC）。
///
/// 用法（必须提供中文调用名）：
/// ```ignore
/// #[timed("插件安装")]
/// pub async fn plugin_install(...) -> Result<..., String> {
///     // 原业务逻辑
/// }
/// ```
///
/// 作者：Xiaoman
/// 创建时间：2026-08-13
#[proc_macro_attribute]
pub fn timed(attr: TokenStream, item: TokenStream) -> TokenStream {
    let func = parse_macro_input!(item as ItemFn);

    if attr.is_empty() {
        return syn::Error::new_spanned(
            &func.sig.ident,
            "#[timed] 必须提供中文调用名，例如 #[timed(\"插件安装\")]",
        )
        .to_compile_error()
        .into();
    }

    let name_lit = parse_macro_input!(attr as LitStr);
    if name_lit.value().trim().is_empty() {
        return syn::Error::new_spanned(&name_lit, "#[timed] 调用名不能为空")
            .to_compile_error()
            .into();
    }

    if func.sig.asyncness.is_none() {
        return syn::Error::new_spanned(func.sig.fn_token, "#[timed] 仅支持 async fn")
            .to_compile_error()
            .into();
    }

    let name = name_lit.value();

    let attrs = &func.attrs;
    let vis = &func.vis;
    let sig = &func.sig;
    let block = &func.block;

    quote! {
        #(#attrs)*
        #vis #sig {
            crate::app::timing::timed_run(#name, async #block).await
        }
    }
    .into()
}

/// Runtime 生命周期标记 — 自动状态转移 + `[runtime]` 日志（opt-in）。
///
/// 用法：
/// ```ignore
/// #[runtime(python, start = Starting, ok = Ready, err = Failed)]
/// pub async fn ensure_running(&self) -> Result<(), SidecarLifecycleError> {
///     self.process.ensure_running().await
/// }
///
/// #[runtime(agent, start = Stopping, ok = Stopped)]
/// pub fn stop(&self) {}
/// ```
///
/// - `scope`：`python` / `agent` / `runtime`
/// - `start` / `ok`：必填状态变体
/// - `err`：可选；仅当返回 `Result` 且失败时设置
///
/// `runtime` scope 调用 `self.set_state(RuntimeState::…)`（Supervisor）；
/// 其余 scope 调用 `self.lifecycle.set` / `transition`。
#[proc_macro_attribute]
pub fn runtime(attr: TokenStream, item: TokenStream) -> TokenStream {
    let args = parse_macro_input!(attr as RuntimeArgs);
    let func = parse_macro_input!(item as ItemFn);

    match expand_runtime(args, func) {
        Ok(tokens) => tokens.into(),
        Err(error) => error.to_compile_error().into(),
    }
}

struct RuntimeArgs {
    scope: Ident,
    start: Ident,
    ok: Ident,
    err: Option<Ident>,
}

impl Parse for RuntimeArgs {
    fn parse(input: ParseStream<'_>) -> syn::Result<Self> {
        let scope: Ident = input.parse()?;
        input.parse::<Token![,]>()?;

        let mut start: Option<Ident> = None;
        let mut ok: Option<Ident> = None;
        let mut err: Option<Ident> = None;

        while !input.is_empty() {
            let key: Ident = input.parse()?;
            input.parse::<Token![=]>()?;
            let value: Ident = input.parse()?;
            match key.to_string().as_str() {
                "start" => start = Some(value),
                "ok" => ok = Some(value),
                "err" => err = Some(value),
                other => {
                    return Err(syn::Error::new(
                        key.span(),
                        format!("未知参数 `{other}`，仅支持 start / ok / err"),
                    ));
                }
            }
            if input.peek(Token![,]) {
                input.parse::<Token![,]>()?;
            }
        }

        Ok(Self {
            scope,
            start: start.ok_or_else(|| {
                syn::Error::new(proc_macro2::Span::call_site(), "缺少 start = ...")
            })?,
            ok: ok
                .ok_or_else(|| syn::Error::new(proc_macro2::Span::call_site(), "缺少 ok = ..."))?,
            err,
        })
    }
}

fn expand_runtime(args: RuntimeArgs, func: ItemFn) -> syn::Result<proc_macro2::TokenStream> {
    let scope = args.scope.to_string();
    let start = &args.start;
    let ok = &args.ok;
    let start_label = phase_label(&start.to_string());
    let ok_label = phase_label(&ok.to_string());
    let err_label = args
        .err
        .as_ref()
        .map(|ident| phase_label(&ident.to_string()));

    let is_async = func.sig.asyncness.is_some();
    let returns_result = returns_result(&func.sig.output);

    let attrs = &func.attrs;
    let vis = &func.vis;
    let sig = &func.sig;
    let block = &func.block;
    let scope_lit = scope.as_str();

    let apply_state = |variant: &Ident| -> syn::Result<proc_macro2::TokenStream> {
        match scope.as_str() {
            "python" => Ok(quote! {
                self.lifecycle.set(crate::infrastructure::sidecar::PythonState::#variant);
            }),
            "agent" => Ok(quote! {
                self.lifecycle.transition(crate::infrastructure::sidecar::AgentState::#variant);
            }),
            "runtime" => Ok(quote! {
                self.set_state(crate::core::supervisor::RuntimeState::#variant);
            }),
            other => Err(syn::Error::new(
                args.scope.span(),
                format!("不支持的 scope `{other}`，当前仅支持 python / agent / runtime"),
            )),
        }
    };

    let begin_set = apply_state(start)?;
    let ok_set = apply_state(ok)?;
    let begin = quote! {
        #begin_set
        crate::infrastructure::runtime::mark::phase(#scope_lit, #start_label);
    };

    let body = if is_async {
        quote! { async #block .await }
    } else {
        quote! { #block }
    };

    let finish = if returns_result {
        if let Some(err) = &args.err {
            let err_label = err_label.expect("err_label");
            let err_set = apply_state(err)?;
            quote! {
                match &__runtime_result {
                    Ok(_) => {
                        #ok_set
                        crate::infrastructure::runtime::mark::phase(#scope_lit, #ok_label);
                    }
                    Err(_) => {
                        #err_set
                        crate::infrastructure::runtime::mark::phase(#scope_lit, #err_label);
                    }
                }
            }
        } else {
            quote! {
                if __runtime_result.is_ok() {
                    #ok_set
                    crate::infrastructure::runtime::mark::phase(#scope_lit, #ok_label);
                }
            }
        }
    } else {
        if let Some(err) = &args.err {
            return Err(syn::Error::new(err.span(), "非 Result 返回值不能指定 err"));
        }
        quote! {
            #ok_set
            crate::infrastructure::runtime::mark::phase(#scope_lit, #ok_label);
        }
    };

    Ok(quote! {
        #(#attrs)*
        #vis #sig {
            #begin
            let __runtime_result = #body;
            #finish
            __runtime_result
        }
    })
}

fn returns_result(output: &syn::ReturnType) -> bool {
    match output {
        syn::ReturnType::Default => false,
        syn::ReturnType::Type(_, ty) => match ty.as_ref() {
            syn::Type::Path(path) => path
                .path
                .segments
                .last()
                .map(|seg| seg.ident == "Result")
                .unwrap_or(false),
            _ => false,
        },
    }
}

/// WSS 桥：更新本地 session 并推送连接状态。
///
/// ```ignore
/// macros::apply_conn_state!(coordinator, sessions, account_id, ConnectionState::Connected);
/// macros::apply_conn_state!(coordinator, sessions, account_id, ConnectionState::Error, detail);
/// ```
#[proc_macro]
pub fn apply_conn_state(input: TokenStream) -> TokenStream {
    let args = parse_macro_input!(input as ApplyConnStateArgs);
    let coord = &args.coord;
    let sessions = &args.sessions;
    let account_id = &args.account_id;
    let state = &args.state;
    let detail = match &args.detail {
        Some(detail) => quote! { ::core::option::Option::Some(#detail) },
        None => quote! { ::core::option::Option::None },
    };
    quote! {{
        update_session_state(#sessions, #account_id, #state).await;
        InboundListener::on_state(#coord, #account_id, #state, #detail).await;
    }}
    .into()
}

struct ApplyConnStateArgs {
    coord: syn::Expr,
    sessions: syn::Expr,
    account_id: syn::Expr,
    state: syn::Expr,
    detail: Option<syn::Expr>,
}

impl Parse for ApplyConnStateArgs {
    fn parse(input: ParseStream<'_>) -> syn::Result<Self> {
        let coord: syn::Expr = input.parse()?;
        input.parse::<Token![,]>()?;
        let sessions: syn::Expr = input.parse()?;
        input.parse::<Token![,]>()?;
        let account_id: syn::Expr = input.parse()?;
        input.parse::<Token![,]>()?;
        let state: syn::Expr = input.parse()?;
        let detail = if input.peek(Token![,]) {
            input.parse::<Token![,]>()?;
            if input.is_empty() {
                None
            } else {
                let expr: syn::Expr = input.parse()?;
                Some(expr)
            }
        } else {
            None
        };
        if !input.is_empty() {
            return Err(input.error("多余参数"));
        }
        Ok(Self {
            coord,
            sessions,
            account_id,
            state,
            detail,
        })
    }
}

fn phase_label(variant: &str) -> String {
    match variant {
        "Starting" => "start".to_string(),
        "Stopping" => "stop".to_string(),
        "Restarting" => "restart".to_string(),
        other => {
            let mut out = String::new();
            for (index, ch) in other.chars().enumerate() {
                if ch.is_uppercase() {
                    if index > 0 {
                        out.push('_');
                    }
                    out.extend(ch.to_lowercase());
                } else {
                    out.push(ch);
                }
            }
            out
        }
    }
}
