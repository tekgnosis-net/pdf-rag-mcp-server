import React from 'react';  
import {  
  Box,  
  Progress,  
  Text,  
  HStack,  
  Tooltip,  
  Badge  
} from '@chakra-ui/react';  

const ProgressBar = ({ value, status, showPercentage = true, size = "md", colorScheme = "blue" }) => {  
  // 设置进度条颜色  
  let barColor = colorScheme;  
  if (status?.toLowerCase().includes('error')) {  
    barColor = "red";  
  } else if (value >= 100) {  
    barColor = "green";  
  }  

  // 格式化状态文本  
  const statusText = status || (value >= 100 ? "Completed" : "Processing");  
  
  return (  
    <Box width="100%">  
      <HStack mb={1} justify="space-between">  
        {status && (  
          <Tooltip label={statusText}>  
            <Badge colorScheme={barColor} fontSize="xs">  
              {statusText.length > 20 ? `${statusText.substring(0, 20)}...` : statusText}  
            </Badge>  
          </Tooltip>  
        )}  
        
        {showPercentage && (  
          <Text fontSize="xs" fontWeight="medium" ml="auto">  
            {Math.round(value)}%  
          </Text>  
        )}  
      </HStack>  
      
      <Progress   
        value={value}   
        size={size}   
        colorScheme={barColor}  
        borderRadius="full"  
        hasStripe={value < 100 && value > 0}  
        isAnimated={value < 100 && value > 0}  
      />  
    </Box>  
  );  
};  

export default ProgressBar;