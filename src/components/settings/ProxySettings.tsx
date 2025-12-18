import { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useTranslation } from 'react-i18next';

// 代理设置接口定义
interface ProxySettings {
  enabled: boolean;
  proxy_type: 'http' | 'socks5';
  host: string;
  port: number;
  username?: string;
  password?: string;
}

/**
 * 网络代理设置组件
 *
 * 功能：
 * - 配置 HTTP/SOCKS5 代理
 * - 代理认证支持
 * - 保存前测试连接
 * - 实时生效（热更新）
 */
export default function ProxySettings() {
  const { t } = useTranslation();

  // 状态管理
  const [settings, setSettings] = useState<ProxySettings>({
    enabled: false,
    proxy_type: 'http',
    host: '',
    port: 0,
    username: '',
    password: '',
  });

  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // 组件挂载时加载配置
  useEffect(() => {
    loadSettings();
  }, []);

  // 加载当前代理配置
  const loadSettings = async () => {
    try {
      const config = await invoke<ProxySettings>('get_proxy_settings');
      setSettings(config);
    } catch (error) {
      console.error('加载代理配置失败:', error);
      showMessage('error', `加载配置失败: ${error}`);
    }
  };

  // 显示提示信息
  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 5000);
  };

  // 测试代理连接
  const handleTest = async () => {
    if (!settings.host || settings.port === 0) {
      showMessage('error', '请先填写代理服务器地址和端口');
      return;
    }

    setTesting(true);
    try {
      const result = await invoke<string>('test_proxy_connection', { settings });
      showMessage('success', result);
    } catch (error) {
      showMessage('error', `${error}`);
    } finally {
      setTesting(false);
    }
  };

  // 保存代理设置
  const handleSave = async () => {
    setSaving(true);
    try {
      await invoke('save_proxy_settings', { settings });
      showMessage('success', '代理设置已保存并立即生效！');
    } catch (error) {
      showMessage('error', `${error}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 提示消息 */}
      {message && (
        <div className={`alert ${message.type === 'success' ? 'alert-success' : 'alert-error'}`}>
          <span>{message.text}</span>
        </div>
      )}

      {/* 启用开关 */}
      <div className="form-control">
        <label className="label cursor-pointer justify-start gap-4">
          <input
            type="checkbox"
            className="toggle toggle-primary"
            checked={settings.enabled}
            onChange={(e) => setSettings({ ...settings, enabled: e.target.checked })}
          />
          <span className="label-text text-base font-medium">
            {t('settings.proxy.enable', '启用网络代理')}
          </span>
        </label>
        <p className="text-sm text-base-content/60 mt-1">
          启用后，所有网络请求将通过配置的代理服务器
        </p>
      </div>

      {/* 代理类型 */}
      <div className="form-control">
        <label className="label">
          <span className="label-text">{t('settings.proxy.type', '代理类型')}</span>
        </label>
        <select
          className="select select-bordered w-full"
          value={settings.proxy_type}
          onChange={(e) => setSettings({ ...settings, proxy_type: e.target.value as 'http' | 'socks5' })}
          disabled={!settings.enabled}
        >
          <option value="http">HTTP</option>
          <option value="socks5">SOCKS5</option>
        </select>
      </div>

      {/* 服务器地址 */}
      <div className="grid grid-cols-2 gap-4">
        <div className="form-control">
          <label className="label">
            <span className="label-text">{t('settings.proxy.host', '服务器地址')}</span>
          </label>
          <input
            type="text"
            className="input input-bordered w-full"
            placeholder="127.0.0.1"
            value={settings.host}
            onChange={(e) => setSettings({ ...settings, host: e.target.value })}
            disabled={!settings.enabled}
          />
        </div>

        <div className="form-control">
          <label className="label">
            <span className="label-text">{t('settings.proxy.port', '端口')}</span>
          </label>
          <input
            type="number"
            className="input input-bordered w-full"
            placeholder="1080"
            value={settings.port || ''}
            onChange={(e) => setSettings({ ...settings, port: parseInt(e.target.value) || 0 })}
            disabled={!settings.enabled}
            min="1"
            max="65535"
          />
        </div>
      </div>

      {/* 认证信息（可选） */}
      <div className="divider">认证信息（可选）</div>

      <div className="grid grid-cols-2 gap-4">
        <div className="form-control">
          <label className="label">
            <span className="label-text">
              {t('settings.proxy.username', '用户名')}
              <span className="text-base-content/50 text-xs ml-2">({t('common.optional', '可选')})</span>
            </span>
          </label>
          <input
            type="text"
            className="input input-bordered w-full"
            value={settings.username || ''}
            onChange={(e) => setSettings({ ...settings, username: e.target.value })}
            disabled={!settings.enabled}
          />
        </div>

        <div className="form-control">
          <label className="label">
            <span className="label-text">
              {t('settings.proxy.password', '密码')}
              <span className="text-base-content/50 text-xs ml-2">({t('common.optional', '可选')})</span>
            </span>
          </label>
          <input
            type="password"
            className="input input-bordered w-full"
            value={settings.password || ''}
            onChange={(e) => setSettings({ ...settings, password: e.target.value })}
            disabled={!settings.enabled}
          />
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex gap-3 pt-4">
        <button
          className="btn btn-outline btn-sm"
          onClick={handleTest}
          disabled={!settings.enabled || testing}
        >
          {testing ? (
            <>
              <span className="loading loading-spinner loading-sm"></span>
              {t('settings.proxy.testing', '测试中...')}
            </>
          ) : (
            t('settings.proxy.test', '测试连接')
          )}
        </button>

        <button
          className="btn btn-primary btn-sm"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? (
            <>
              <span className="loading loading-spinner loading-sm"></span>
              {t('common.saving', '保存中...')}
            </>
          ) : (
            t('common.save', '保存设置')
          )}
        </button>
      </div>

      {/* 使用提示 */}
      <div className="alert alert-info mt-6">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-current shrink-0 w-6 h-6">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
        </svg>
        <div className="text-sm">
          <p className="font-semibold">提示：</p>
          <ul className="list-disc list-inside space-y-1 mt-1">
            <li>保存前会自动测试代理连接，确保代理可用</li>
            <li>配置修改后立即生效，无需重启应用</li>
            <li>代理连接失败时，网络请求会直接报错</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
