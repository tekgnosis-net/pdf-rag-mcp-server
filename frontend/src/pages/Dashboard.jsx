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
    // Set up refresh interval  
    const intervalId = setInterval(fetchDocuments, 10000);  
    return () => clearInterval(intervalId);  
  }, []);  

  // Merge document status with WebSocket status  
  const enhancedDocuments = documents.map(doc => {  
    const wsStatus = processingStatus[doc.filename];  
    return {  
      ...doc,  
      // Update progress with WebSocket status if available  
      progress: wsStatus ? wsStatus.progress : doc.progress,  
      statusText: wsStatus ? wsStatus.status : (doc.processed ? "Completed" : "Processing"),  
    };  
  });  

  // Separate processed and processing documents  
  const processedDocs = enhancedDocuments.filter(doc => doc.processed);  
  const processingDocs = enhancedDocuments.filter(doc => !doc.processed);  

  const handleFileUploaded = () => {  
    // Refresh document list  
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
          Configure in Cursor: Settings → AI & MCP → Add URL: http://localhost:7800/mcp  
        </Text>  
      </Box>  
    </Box>  
  );  
};  

export default Dashboard;