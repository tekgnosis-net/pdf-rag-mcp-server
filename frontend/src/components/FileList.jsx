import React from 'react';  
import {   
  Box,   
  Table,   
  Thead,   
  Tbody,   
  Tr,   
  Th,   
  Td,   
  IconButton,   
  Badge,  
  Tooltip,  
  Text,  
  HStack,  
  useToast  
} from '@chakra-ui/react';  
import { FiTrash, FiInfo } from 'react-icons/fi';  
import axios from 'axios';  
import { formatDistance } from 'date-fns';  
import ProgressBar from './ProgressBar';  


const FileList = ({ documents, onDeleteDocument, showProgress }) => {  
  const toast = useToast();  

  const handleDelete = async (id, filename) => {  
    try {  
      await axios.delete(`/api/documents/${id}`);  
      toast({  
        title: "Document deleted",  
        description: `${filename} has been deleted successfully`,  
        status: "success",  
        duration: 3000,  
        isClosable: true,  
      });  
      if (onDeleteDocument) onDeleteDocument();  
    } catch (error) {  
      console.error("Delete error:", error);  
      toast({  
        title: "Delete failed",  
        description: error.response?.data?.detail || "Failed to delete document",  
        status: "error",  
        duration: 5000,  
        isClosable: true,  
      });  
    }  
  };  

  const formatFileSize = (bytes) => {  
    if (bytes < 1024) return bytes + ' B';  
    else if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';  
    else return (bytes / 1048576).toFixed(1) + ' MB';  
  };  

  const getStatusBadge = (doc) => {  
    if (doc.error) {  
      return <Badge colorScheme="red">Error</Badge>;  
    }  
    
    if (doc.processed) {  
      return <Badge colorScheme="green">Completed</Badge>;  
    }  
    
    if (doc.processing) {  
      return <Badge colorScheme="blue">Processing</Badge>;  
    }  
    
    return <Badge colorScheme="yellow">Queued</Badge>;  
  };  

  return (  
    <Box overflowX="auto">  
      <Table variant="simple" size="sm">  
        <Thead>  
          <Tr>  
            <Th>Filename</Th>  
            <Th>Uploaded</Th>  
            <Th>Size</Th>  
            <Th>Status</Th>  
            {showProgress && (<Th>Progress</Th>)}  
            <Th>Actions</Th>  
          </Tr>  
        </Thead>  
        <Tbody>  
          {documents.map((doc) => (  
            <Tr key={doc.id}>  
              <Td fontWeight="medium">{doc.filename}</Td>  
              <Td>  
                {formatDistance(new Date(doc.uploaded_at), new Date(), { addSuffix: true })}  
              </Td>  
              <Td>{formatFileSize(doc.file_size)}</Td>  
              <Td>  
                <HStack spacing={2}>  
                  {getStatusBadge(doc)}  
                  {doc.error && (  
                    <Tooltip label={doc.error}>  
                      <IconButton  
                        icon={<FiInfo />}  
                        aria-label="Error details"  
                        size="xs"  
                        colorScheme="red"  
                        variant="ghost"  
                      />  
                    </Tooltip>  
                  )}  
                </HStack>  
              </Td>  
              {showProgress && (  
                <Td>  
                  <Box>  
                    <ProgressBar   
                      value={doc.progress}   
                      status={doc.statusText}   
                      colorScheme={doc.error ? "red" : "blue"}  
                    />  
                  </Box>  
                </Td>  
              )}  
              <Td>  
                <IconButton  
                  icon={<FiTrash />}  
                  aria-label="Delete document"  
                  size="sm"  
                  colorScheme="red"  
                  variant="ghost"  
                  isDisabled={doc.processing}  
                  onClick={() => handleDelete(doc.id, doc.filename)}  
                />  
              </Td>  
            </Tr>  
          ))}  
        </Tbody>  
      </Table>  
    </Box>  
  );  
};  

export default FileList;