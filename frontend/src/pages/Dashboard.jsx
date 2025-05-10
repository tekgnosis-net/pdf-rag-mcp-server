import React, { useEffect, useState } from 'react';  
import {   
  Box,   
  Heading,   
  SimpleGrid,   
  useToast,   
  Tabs,   
  TabList,   
  Tab,   
  TabPanels,   
  TabPanel,  
  Text  
} from '@chakra-ui/react';  
import axios from 'axios';  
import FileUpload from '../components/FileUpload';  
import FileList from '../components/FileList';  
import { useWebSocket } from '../context/WebSocketContext';  

const Dashboard = () => {  
  const [documents, setDocuments] = useState([]);  
  const [loading, setLoading] = useState(true);  
  const { processingStatus, isConnected } = useWebSocket();  
  const toast = useToast();  

  const fetchDocuments = async () => {  
    try {  
      const response = await axios.get('/api/documents');  
      setDocuments(response.data);  
    } catch (error) {  
      console.error("Failed to fetch documents:", error);  
      toast({  
        title: "Error",  
        description: "Failed to fetch documents",  
        status: "error",  
        duration: 5000,  
        isClosable: true,  
      });  
    } finally {  
      setLoading(false);  
    }  
  };  

  useEffect(() => {  
    fetchDocuments();  
    // 设置定时刷新  
    const intervalId = setInterval(fetchDocuments, 10000);  
    return () => clearInterval(intervalId);  
  }, []);  

  // 合并文档状态与WebSocket状态  
  const enhancedDocuments = documents.map(doc => {  
    const wsStatus = processingStatus[doc.filename];  
    return {  
      ...doc,  
      // 使用WebSocket状态更新进度（如果可用）  
      progress: wsStatus ? wsStatus.progress : doc.progress,  
      statusText: wsStatus ? wsStatus.status : (doc.processed ? "Completed" : "Processing"),  
    };  
  });  

  // 分离已处理和处理中的文档  
  const processedDocs = enhancedDocuments.filter(doc => doc.processed);  
  const processingDocs = enhancedDocuments.filter(doc => !doc.processed);  

  const handleFileUploaded = () => {  
    // 刷新文档列表  
    fetchDocuments();  
  };  

  return (  
    <Box>  
      <Heading as="h1" size="xl" mb={6}>MCP PDF Knowledge Base</Heading>  
      
      <Box mb={8}>  
        <Heading as="h2" size="md" mb={3}>Upload New PDF</Heading>  
        <FileUpload onFileUploaded={handleFileUploaded} />  
      </Box>  
      
      <Box bg="white" p={5} shadow="md" borderRadius="md" mb={4}>  
        <Heading as="h2" size="md" mb={4}>Your Documents</Heading>  
        
        <Tabs variant="enclosed" colorScheme="blue">  
          <TabList>  
            <Tab>Processing ({processingDocs.length})</Tab>  
            <Tab>Completed ({processedDocs.length})</Tab>  
          </TabList>  
          
          <TabPanels>  
            <TabPanel px={0}>  
              {processingDocs.length > 0 ? (  
                <FileList   
                  documents={processingDocs}   
                  onDeleteDocument={fetchDocuments}   
                  showProgress={true}  
                />  
              ) : (  
                <Text color="gray.500">No documents currently processing</Text>  
              )}  
            </TabPanel>  
            
            <TabPanel px={0}>  
              {processedDocs.length > 0 ? (  
                <FileList   
                  documents={processedDocs}   
                  onDeleteDocument={fetchDocuments}   
                  showProgress={false}  
                />  
              ) : (  
                <Text color="gray.500">No processed documents yet</Text>  
              )}  
            </TabPanel>  
          </TabPanels>  
        </Tabs>  
      </Box>  
      
      <Box bg="white" p={5} shadow="md" borderRadius="md">  
        <Heading as="h2" size="md" mb={3}>MCP Connection Status</Heading>  
        <Text   
          color={isConnected ? "green.500" : "red.500"}   
          fontWeight="medium"  
        >  
          {isConnected ? "Connected" : "Disconnected"}  
        </Text>  
        <Text fontSize="sm" color="gray.600" mt={2}>  
          Configure in Cursor: Settings → AI & MCP → Add URL: http://localhost:8000/mcp/v1  
        </Text>  
      </Box>  
    </Box>  
  );  
};  

export default Dashboard;