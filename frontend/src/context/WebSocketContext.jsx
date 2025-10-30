import React, { createContext, useContext, useEffect, useState } from 'react';  
import { useToast } from '@chakra-ui/react';  

const WebSocketContext = createContext(null);  

export const useWebSocket = () => useContext(WebSocketContext);  

export const WebSocketProvider = ({ children }) => {  
  const [socket, setSocket] = useState(null);  
  const [isConnected, setIsConnected] = useState(false);  
  const [processingStatus, setProcessingStatus] = useState({});  
  const toast = useToast();  

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
  }, [toast]);  

  return (  
    <WebSocketContext.Provider value={{ isConnected, processingStatus }}>  
      {children}  
    </WebSocketContext.Provider>  
  );  
};