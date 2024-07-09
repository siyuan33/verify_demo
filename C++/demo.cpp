#include <iostream>
using namespace std;

class Line
{
public:
    void setLength(double len);
    double getLength(void);
    Line(double len1, double len2) : length(len1), length2(len2)
    {
        cout << "Object is being created, length = " << len1 << endl;
        // length = len;
    }; // 这是构造函数

private:
    double length;
    double length2;
};

void Line::setLength(double len)
{
    length = len;
}

double Line::getLength(void)
{
    return length;
}
// 程序的主函数
int main()
{
    Line line(10.0, 20.0);

    // 获取默认设置的长度
    cout << "Length of line : " << line.getLength() << endl;
    // 再次设置长度
    line.setLength(6.0);
    cout << "Length of line : " << line.getLength() << endl;

    return 0;
}
// cout << value << endl;
