import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';  
import { useToast } from '@chakra-ui/react';  
import axios from 'axios';  

const WebSocketContext = createContext(null);  

export const useWebSocket = () => useContext(WebSocketContext);  

export const WebSocketProvider = ({ children }) => {  
  const [socket, setSocket] = useState(null);  
  const [isConnected, setIsConnected] = useState(false);  
  const [processingStatus, setProcessingStatus] = useState({});  
  const [connectionSnapshot, setConnectionSnapshot] = useState({
    generatedAt: null,
    websocketClients: [],
    mcpSessions: [],
  });
  const toast = useToast();  

  const applySnapshot = useCallback((payload) => {
    if (!payload || typeof payload !== 'object') {
      return;
    }

    setConnectionSnapshot({
      generatedAt: payload.generated_at ?? null,
      websocketClients: Array.isArray(payload.websocket_clients) ? payload.websocket_clients : [],
      mcpSessions: Array.isArray(payload.mcp_sessions) ? payload.mcp_sessions : [],
    });
  }, []);

  const refreshSnapshot = useCallback(async () => {
    try {
      const { data } = await axios.get('/api/connections');
      applySnapshot(data);
    } catch (error) {
      // Surface via console to avoid noisy toasts for routine polling failures
      console.error('Failed to refresh connection snapshot', error);
    }
  }, [applySnapshot]);

  useEffect(() => {  
    let ws;
    let reconnectTimer;
    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const portSegment = window.location.port ? `:${window.location.port}` : '';
  ws = new window.WebSocket(`${protocol}://${window.location.hostname}${portSegment}/ws`);
      setSocket(ws);
      ws.onopen = () => {  
        setIsConnected(true);  
        toast({  
          title: "Connected to server",  
          status: "success",  
          duration: 3000,  
          isClosable: true,  
        });  
        refreshSnapshot();
      };  
  
      ws.onmessage = (event) => {  
        const data = JSON.parse(event.data);  
        if (data.type === 'initial_status') {  
          setProcessingStatus(data.status);  
        } else if (data.type === 'processing_update') {  
          setProcessingStatus(prev => ({  
            ...prev,  
            [data.filename]: data.status  
          }));  
        } else if (data.type === 'connection_snapshot') {
          applySnapshot(data);
        }  
      };  
  
      ws.onclose = () => {  
        setIsConnected(false);  
        toast({  
          title: "Disconnected from server",  
          status: "warning",  
          duration: 3000,  
          isClosable: true,  
        });  
        refreshSnapshot();
        // Try to reconnect after 3 seconds
        reconnectTimer = setTimeout(() => {
          connect();
        }, 3000);
      };  
  
      ws.onerror = (error) => {  
        console.error("WebSocket error:", error);  
        toast({  
          title: "WebSocket error",  
          description: "Failed to connect to server",  
          status: "error",  
          duration: 5000,  
          isClosable: true,  
        });  
      };  
    };
    connect();
    // Cleanup function  
    return () => {  
      if (ws && ws.readyState === WebSocket.OPEN) {  
        ws.close();  
      }  
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
    };  
  }, [applySnapshot, refreshSnapshot, toast]);  

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      refreshSnapshot();
    }, 15000);

    return () => {
      if (intervalId) {
        window.clearInterval(intervalId);
      }
    };
  }, [refreshSnapshot]);

  return (  
    <WebSocketContext.Provider value={{
      isConnected,
      processingStatus,
      connectionSnapshot,
      refreshConnectionSnapshot: refreshSnapshot,
    }}>  
      {children}  
    </WebSocketContext.Provider>  
  );  
};