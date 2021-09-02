from testciadapter import (TestCIAdapterGood, TestCIAdapterBad1, TestCIAdapterBad2)
from abstractciadapter import (CIAdapterCheckError, check_adapter)

print ("Checking TestCIAdapterBad1:")
try:
    check_adapter (TestCIAdapterBad1 ("test"))
    raise CIAdapterCheckError("The check_adapter(TestCIAdapterBad1) hasn't failed as expected!")
except CIAdapterCheckError as e:
    print ("    %s (as expected)" % e)

print ("Checking TestCIAdapterBad2:")
try:
    check_adapter (TestCIAdapterBad2 ("test"))
    raise CIAdapterCheckError("The check_adapter(TestCIAdapterBad2) hasn't failed as expected!")
except CIAdapterCheckError as e:
    print ("    %s (as expected)" % e)

print ("Checking TestCIAdapterGood:")
check_adapter (TestCIAdapterGood ("test"))
print ("Test PASSED")
