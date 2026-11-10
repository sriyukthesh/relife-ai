import { useEffect, useState } from "react";
import { api } from "../api";

interface PayPalConfig {
  client_id: string;
  currency: string;
  seller_email: string;
  enabled: boolean;
}

interface PayPalButtonData {
  orderID: string;
}

interface PayPalButtonsOptions {
  style: { layout: "vertical"; label: "paypal" };
  createOrder: () => Promise<string>;
  onApprove: (data: PayPalButtonData) => Promise<void>;
  onError: (error: unknown) => void;
}

interface PayPalButtonsInstance {
  render: (container: HTMLElement) => Promise<void>;
  close: () => void;
}

interface PayPalSdk {
  Buttons: (options: PayPalButtonsOptions) => PayPalButtonsInstance;
}

declare global {
  interface Window {
    paypal?: PayPalSdk;
  }
}

let sdkPromise: Promise<PayPalSdk> | null = null;

function loadSdk(config: PayPalConfig): Promise<PayPalSdk> {
  if (window.paypal) return Promise.resolve(window.paypal);
  if (sdkPromise) return sdkPromise;

  const promise = new Promise<PayPalSdk>((resolve, reject) => {
    const script = document.createElement("script");
    const params = new URLSearchParams({
      "client-id": config.client_id,
      currency: config.currency,
      intent: "capture",
      components: "buttons",
    });
    script.src = `https://www.paypal.com/sdk/js?${params}`;
    script.async = true;
    script.onload = () => {
      if (window.paypal) resolve(window.paypal);
      else reject(new Error("PayPal checkout could not be loaded."));
    };
    script.onerror = () => reject(new Error("Unable to load PayPal checkout. Check your connection."));
    document.head.appendChild(script);
  });
  const retryablePromise = promise.catch((error: unknown) => {
    sdkPromise = null;
    throw error;
  });
  sdkPromise = retryablePromise;
  return retryablePromise;
}

export default function PayPalButtons({
  onCreateOrder,
  onApprove,
  onError,
}: {
  onCreateOrder: () => Promise<string>;
  onApprove: (orderId: string) => Promise<void>;
  onError: (error: unknown) => void;
}) {
  const [config, setConfig] = useState<PayPalConfig | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [host, setHost] = useState<HTMLDivElement | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let active = true;
    setConfig(null);
    setMessage(null);
    api.paypalConfig().then((value) => {
      if (!active) return;
      if (!value.enabled || !value.client_id) {
        setMessage("PayPal sandbox is not configured. Add the sandbox client ID and secret to the backend environment.");
        return;
      }
      setConfig(value);
    }).catch((error: unknown) => {
      if (active) setMessage(error instanceof Error ? error.message : "Could not load PayPal configuration.");
    });
    return () => { active = false; };
  }, [retryCount]);

  useEffect(() => {
    if (!config || !host) return;
    let active = true;
    let buttons: PayPalButtonsInstance | null = null;
    loadSdk(config).then(async (sdk) => {
      if (!active) return;
      buttons = sdk.Buttons({
        style: { layout: "vertical", label: "paypal" },
        createOrder: onCreateOrder,
        onApprove: async (data) => {
          try {
            await onApprove(data.orderID);
          } catch (err) {
            onError(err);
          }
        },
        onError,
      });
      await buttons.render(host);
    }).catch((error: unknown) => {
      if (active) {
        setMessage(error instanceof Error ? error.message : "PayPal checkout could not be loaded.");
        onError(error);
      }
    });
    return () => {
      active = false;
      buttons?.close();
    };
  }, [config, host, onApprove, onCreateOrder, onError]);

  if (!config) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
          PayPal sandbox
        </span>
        {config.seller_email && (
          <span className="text-xs text-stone-500">Seller: {config.seller_email}</span>
        )}
      </div>
      {message && <p role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">{message}</p>}
      {message && <button className="btn-ghost mt-2" onClick={() => setRetryCount((count) => count + 1)}>Retry PayPal connection</button>}
      <div ref={setHost} />
    </div>
  );
}
