import React, { useMemo } from 'react';  
import {  
  Box,  
  Progress,  
  Text,  
  HStack,  
  Tooltip,  
  Badge  
} from '@chakra-ui/react';  
 
const ProgressBar = ({ progress = 0, status = "Processing...", pageCurrent = null, pageTotal = null }) => {  
  const numericProgress = Number.isFinite(progress) ? progress : Number(progress) || 0;  
  const value = Math.max(0, Math.min(100, numericProgress));  
  const showPageInfo = Number.isFinite(pageCurrent) && Number.isFinite(pageTotal) && pageTotal > 0;  
  
  // Set progress bar color  
  const colorScheme = useMemo(() => {  
    if (status.toLowerCase().includes('error')) return 'red';  
    if (value === 100) return 'green';  
    return 'blue';  
  }, [value, status]);  
  
  // Format status text  
  const statusText = useMemo(() => {  
    if (status.toLowerCase().includes('error')) {  
      return status.replace('Error:', 'Error:');  
    }  
    return status;  
  }, [status]);  

  const displayPercent = useMemo(() => {  
    if (value >= 10) return Math.round(value).toString();  
    if (value >= 1) return value.toFixed(1);  
    return value.toFixed(2);  
  }, [value]);  
 
  return (  
    <Box width="100%">  
      <HStack mb={1} justify="space-between">  
        {status && (  
          <Tooltip label={statusText}>  
            <Badge colorScheme={colorScheme} fontSize="xs">  
              {statusText.length > 28 ? `${statusText.substring(0, 28)}...` : statusText}  
            </Badge>  
          </Tooltip>  
        )}  
        
        <Text fontSize="xs" fontWeight="medium" ml="auto">  
          {displayPercent}%  
        </Text>  
      </HStack>  

      {showPageInfo && (  
        <Text fontSize="xs" color="gray.500" mb={1}>  
          Page {Math.min(pageCurrent, pageTotal)} of {pageTotal}  
        </Text>  
      )}
      
      <Progress   
        value={value}   
        size="md"   
        colorScheme={colorScheme}  
        borderRadius="full"  
        hasStripe={value < 100 && value > 0}  
        isAnimated={value < 100 && value > 0}  
      />  
    </Box>  
  );  
};  
 
export default ProgressBar;