import React, { useEffect, useState } from 'react';  
import {   
  Box,   
  Heading,   
  Text,   
  Flex,   
  Badge,   
  Divider,   
  Button,  
  VStack,  
  HStack,  
  Stat,  
  StatLabel,  
  StatNumber,  
  StatHelpText,  
  SimpleGrid,  
  IconButton,  
  useToast,  
  Link,  
  Breadcrumb,  
  BreadcrumbItem,  
  BreadcrumbLink  
} from '@chakra-ui/react';  
import { useParams, Link as RouterLink, useNavigate } from 'react-router-dom';  
import { FiArrowLeft, FiTrash, FiRefreshCw, FiDatabase } from 'react-icons/fi';  
import axios from 'axios';  
import { format } from 'date-fns';  
import ProgressBar from '../components/ProgressBar';  
import { useWebSocket } from '../context/WebSocketContext';  

const PDFView = () => {  
  const { id } = useParams();  
  const [document, setDocument] = useState(null);  
  const [loading, setLoading] = useState(true);  
  const { processingStatus } = useWebSocket();  
  const toast = useToast();  
  const navigate = useNavigate();  

  const fetchDocument = async () => {  
    try {  
      const response = await axios.get(`/api/documents/${id}`);  
      setDocument(response.data);  
    } catch (error) {  
      console.error("Failed to fetch document:", error);  
      toast({  
        title: "Error",  
        description: "Failed to fetch document details",  
        status: "error",  
        duration: 5000,  
        isClosable: true,  
      });  
    } finally {  
      setLoading(false);  
    }  
  };  

  useEffect(() => {  
    fetchDocument();  
    // 设置定时刷新  
    const intervalId = setInterval(fetchDocument, 5000);  
    return () => clearInterval(intervalId);  
  }, [id]);  

  const handleDelete = async () => {  
    try {  
      await axios.delete(`/api/documents/${id}`);  
      toast({  
        title: "Document deleted",  
        status: "success",  
        duration: 3000,  
        isClosable: true,  
      });  
      navigate('/');  
    } catch (error) {  
      toast({  
        title: "Delete failed",  
        description: error.response?.data?.detail || "Failed to delete document",  
        status: "error",  
        duration: 5000,  
        isClosable: true,  
      });  
    }  
  };  

  if (loading) {  
    return (  
      <Box textAlign="center" py={10}>  
        <Text>Loading document details...</Text>  
      </Box>  
    );  
  }  

  if (!document) {  
    return (  
      <Box textAlign="center" py={10}>  
        <Heading size="md">Document not found</Heading>  
        <Button as={RouterLink} to="/" mt={4} leftIcon={<FiArrowLeft />}>  
          Back to Dashboard  
        </Button>  
      </Box>  
    );  
  }  

  // 合并WebSocket状态  
  let wsStatus = processingStatus[document.filename];
  if (!wsStatus && document.id) {
    wsStatus = processingStatus[document.id];
  }
  const enhancedDocument = {  
    ...document,  
    progress: wsStatus ? wsStatus.progress : document.progress,  
    statusText: wsStatus ? wsStatus.status : (document.processed ? "Completed" : "Processing"),  
  };  

  const formatFileSize = (bytes) => {  
    if (bytes < 1024) return bytes + ' B';  
    else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';  
    else return (bytes / 1048576).toFixed(1) + ' MB';  
  };  

  return (  
    <Box>  
      <Breadcrumb mb={6}>  
        <BreadcrumbItem>  
          <BreadcrumbLink as={RouterLink} to="/">Dashboard</BreadcrumbLink>  
        </BreadcrumbItem>  
        <BreadcrumbItem isCurrentPage>  
          <BreadcrumbLink>Document Details</BreadcrumbLink>  
        </BreadcrumbItem>  
      </Breadcrumb>  

      <Flex justifyContent="space-between" alignItems="center" mb={6}>  
        <Heading size="lg">{enhancedDocument.filename}</Heading>  
        <Button   
          as={RouterLink}   
          to="/"   
          leftIcon={<FiArrowLeft />}  
          variant="outline"  
        >  
          Back  
        </Button>  
      </Flex>  

      <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6} mb={6}>  
        <Box bg="white" p={5} shadow="md" borderRadius="md">  
          <Heading size="md" mb={4}>Document Information</Heading>  
          <VStack align="stretch" spacing={3}>  
            <Flex justify="space-between">  
              <Text fontWeight="medium">File Size:</Text>  
              <Text>{formatFileSize(enhancedDocument.file_size)}</Text>  
            </Flex>  
            <Flex justify="space-between">  
              <Text fontWeight="medium">Uploaded:</Text>  
              <Text>{format(new Date(enhancedDocument.uploaded_at), 'PPpp')}</Text>  
            </Flex>  
            <Flex justify="space-between">  
              <Text fontWeight="medium">Status:</Text>  
              <Badge colorScheme={enhancedDocument.processed ? "green" : (enhancedDocument.error ? "red" : "blue")}>  
                {enhancedDocument.error ? "Error" : (enhancedDocument.processed ? "Completed" : "Processing")}  
              </Badge>  
            </Flex>  
            {enhancedDocument.error && (  
              <Box>  
                <Text fontWeight="medium" color="red.500">Error:</Text>  
                <Text fontSize="sm" color="red.500">{enhancedDocument.error}</Text>  
              </Box>  
            )}  
          </VStack>  
        </Box>  

        <Box bg="white" p={5} shadow="md" borderRadius="md">  
          <Heading size="md" mb={4}>Processing Details</Heading>  
          <SimpleGrid columns={2} spacing={4} mb={4}>  
            <Stat>  
              <StatLabel>Pages</StatLabel>  
              <StatNumber>{enhancedDocument.page_count}</StatNumber>  
              <StatHelpText>Total pages in document</StatHelpText>  
            </Stat>  
            <Stat>  
              <StatLabel>Text Chunks</StatLabel>  
              <StatNumber>{enhancedDocument.chunks_count}</StatNumber>  
              <StatHelpText>Processed for embedding</StatHelpText>  
            </Stat>  
          </SimpleGrid>  
          
          <Box mt={4}>  
            <Text fontWeight="medium" mb={2}>Processing Progress:</Text>  
            <ProgressBar   
              value={enhancedDocument.progress}   
              status={enhancedDocument.statusText}   
              showPercentage={true}  
            />  
          </Box>  
        </Box>  
      </SimpleGrid>  

      <Box bg="white" p={5} shadow="md" borderRadius="md" mb={6}>  
        <Heading size="md" mb={4}>Actions</Heading>  
        <HStack spacing={4}>  
          <Button   
            leftIcon={<FiRefreshCw />}   
            colorScheme="blue"  
            onClick={fetchDocument}  
          >  
            Refresh Status  
          </Button>  
          <Button   
            leftIcon={<FiTrash />}   
            colorScheme="red"  
            isDisabled={enhancedDocument.processing}  
            onClick={handleDelete}  
          >  
            Delete Document  
          </Button>  
        </HStack>  
      </Box>  

      <Box bg="white" p={5} shadow="md" borderRadius="md">  
        <Heading size="md" mb={4}>MCP Integration</Heading>  
        <Text mb={4}>  
          This document {enhancedDocument.processed ? "is" : "will be"} available through the MCP protocol once processing is complete.  
        </Text>  
        
        <HStack>  
          <IconButton  
            icon={<FiDatabase />}  
            aria-label="MCP connection"  
            colorScheme="purple"  
          />  
          <Text>MCP URL: <Text as="span" fontWeight="bold">http://localhost:8000/mcp/v1</Text></Text>  
        </HStack>  
      </Box>  
    </Box>  
  );  
};  

export default PDFView;