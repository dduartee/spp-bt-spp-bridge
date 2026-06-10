package com.termux.bridge;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothSocket;
import android.content.Context;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.lang.reflect.Method;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;

public class BridgeService extends Service {

    private static final UUID SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB");
    // UUID custom do T470 (SPP via BlueZ D-Bus)
    private static final UUID SPP_UUID_CUSTOM = UUID.fromString("977c4a04-bf68-4c23-bf49-dac84b22d774");
    private static final UUID[] SPP_UUIDS = {SPP_UUID, SPP_UUID_CUSTOM};
    private static final int TCP_PORT = 8090;
    private static final String CHANNEL_ID = "bridge_service";
    private static final int NOTIFY_ID = 1;

    private BluetoothSocket btSocket;
    private ServerSocket tcpServer;
    private Socket tcpClient;
    private final AtomicBoolean running = new AtomicBoolean(false);

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) return START_NOT_STICKY;
        String address = intent.getStringExtra("device_address");
        if (address == null) return START_NOT_STICKY;

        try {
            startForeground(NOTIFY_ID, buildNotification("Conectando..."));
        } catch (Exception e) {
            android.util.Log.e("BridgeService", "startForeground failed: " + e.getMessage());
            // Continue anyway on older Android or if notification permission not granted
        }
        new Thread(new BtConnector(address), "BT-Connect").start();
        return START_STICKY;
    }

    // ---- Named inner classes (D8 crashes on anonymous classes) ----

    private class BtConnector implements Runnable {
        private final String address;
        BtConnector(String address) { this.address = address; }

        public void run() {
            try {
                BluetoothAdapter adapter = BluetoothAdapter.getDefaultAdapter();
                BluetoothDevice device = adapter.getRemoteDevice(address);

                // Tenta múltiplos UUIDs (padrão SPP + custom T470)
                Exception lastError = null;
                for (UUID uuid : SPP_UUIDS) {
                    try {
                        btSocket = device.createRfcommSocketToServiceRecord(uuid);
                        adapter.cancelDiscovery();
                        btSocket.connect();
                        lastError = null;
                        break;
                    } catch (IOException e) {
                        lastError = e;
                        try { if (btSocket != null) btSocket.close(); } catch (Exception ignored) {}
                        btSocket = null;
                    }
                }

                // Fallback: conexão direta via canal RFCOMM (bypass SDP)
                if (btSocket == null) {
                    for (int channel = 1; channel <= 30; channel++) {
                        try {
                            Method m = device.getClass().getMethod("createRfcommSocket", int.class);
                            btSocket = (BluetoothSocket) m.invoke(device, channel);
                            adapter.cancelDiscovery();
                            btSocket.connect();
                            lastError = null;
                            break;
                        } catch (Exception e) {
                            try { if (btSocket != null) btSocket.close(); } catch (Exception ignored) {}
                            btSocket = null;
                        }
                    }
                }

                if (lastError != null) throw new IOException(lastError);

                updateNotification("📱 " + device.getName() + " | 🔌 TCP :" + TCP_PORT);
                startTcpBridge();
                running.set(true);

                // BT → TCP reader
                InputStream btIn = btSocket.getInputStream();
                byte[] buf = new byte[1024];
                while (running.get()) {
                    int len = btIn.read(buf);
                    if (len < 0) break;
                    sendToTcp(buf, len);
                }
            } catch (SecurityException e) {
                updateNotification("❌ Permissão Bluetooth negada");
            } catch (IOException e) {
                updateNotification("❌ Erro: " + e.getMessage());
            } finally {
                stop();
            }
        }
    }

    private class TcpAcceptor implements Runnable {
        public void run() {
            try {
                tcpServer = new ServerSocket(TCP_PORT);
                tcpServer.setReuseAddress(true);
                while (running.get()) {
                    tcpClient = tcpServer.accept();
                    new Thread(new TcpReader(), "TCP2BT").start();
                }
            } catch (IOException e) { /* server stopped */ }
        }
    }

    private class TcpReader implements Runnable {
        public void run() {
            try {
                InputStream tcpIn = tcpClient.getInputStream();
                byte[] buf = new byte[1024];
                OutputStream btOut = btSocket.getOutputStream();
                while (running.get()) {
                    int len = tcpIn.read(buf);
                    if (len < 0) break;
                    btOut.write(buf, 0, len);
                    btOut.flush();
                }
            } catch (IOException e) { /* client disconnected */ }
        }
    }

    // ---- Bridge methods ----

    private void startTcpBridge() {
        Thread t = new Thread(new TcpAcceptor(), "TCP-Accept");
        t.setDaemon(true);
        t.start();
    }

    private void sendToTcp(byte[] data, int len) {
        if (tcpClient != null && tcpClient.isConnected()) {
            try {
                tcpClient.getOutputStream().write(data, 0, len);
                tcpClient.getOutputStream().flush();
            } catch (IOException ignored) {}
        }
    }

    private void stop() {
        running.set(false);
        try { if (btSocket != null) btSocket.close(); } catch (Exception ignored) {}
        try { if (tcpServer != null) tcpServer.close(); } catch (Exception ignored) {}
        try { if (tcpClient != null) tcpClient.close(); } catch (Exception ignored) {}
        stopForeground(true);
        stopSelf();
    }

    @Override
    public void onDestroy() {
        stop();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }

    // ---- Notifications ----

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, "Bridge Service", NotificationManager.IMPORTANCE_LOW);
            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            nm.createNotificationChannel(channel);
        }
    }

    private Notification buildNotification(String text) {
        Intent intent = new Intent(this, MainActivity.class);
        int flags = Build.VERSION.SDK_INT >= 23 ? PendingIntent.FLAG_IMMUTABLE : 0;
        PendingIntent pi = PendingIntent.getActivity(this, 0, intent, flags);
        return new Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("BT SPP Bridge")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_share)
            .setContentIntent(pi)
            .setOngoing(true)
            .build();
    }

    private void updateNotification(String text) {
        NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        nm.notify(NOTIFY_ID, buildNotification(text));
    }
}
