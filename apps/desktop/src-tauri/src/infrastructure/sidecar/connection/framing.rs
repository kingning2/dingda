//! Length-prefix 帧：`[u32 BE length][payload]`。

use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};

use super::error::IpcError;

pub async fn write_frame<W: AsyncWrite + Unpin>(
    writer: &mut W,
    payload: &[u8],
) -> Result<(), IpcError> {
    let len = u32::try_from(payload.len()).map_err(|_| {
        IpcError::ProtocolError(format!("frame too large: {} bytes", payload.len()))
    })?;
    writer.write_all(&len.to_be_bytes()).await.map_err(map_io)?;
    writer.write_all(payload).await.map_err(map_io)?;
    writer.flush().await.map_err(map_io)?;
    Ok(())
}

pub async fn read_frame<R: AsyncRead + Unpin>(reader: &mut R) -> Result<Vec<u8>, IpcError> {
    let mut len_buf = [0u8; 4];
    reader.read_exact(&mut len_buf).await.map_err(map_io)?;
    let len = u32::from_be_bytes(len_buf) as usize;
    if len > 16 * 1024 * 1024 {
        return Err(IpcError::ProtocolError(format!(
            "frame length {len} exceeds 16MiB limit"
        )));
    }
    let mut buf = vec![0u8; len];
    reader.read_exact(&mut buf).await.map_err(map_io)?;
    Ok(buf)
}

fn map_io(err: std::io::Error) -> IpcError {
    match err.kind() {
        std::io::ErrorKind::UnexpectedEof
        | std::io::ErrorKind::ConnectionReset
        | std::io::ErrorKind::BrokenPipe
        | std::io::ErrorKind::NotConnected => IpcError::TransportClosed,
        _ => IpcError::ConnectionFailed(err.to_string()),
    }
}
